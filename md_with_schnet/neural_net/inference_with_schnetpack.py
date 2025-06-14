import os
import argparse
import torch
import schnetpack as spk


from hydra import initialize, compose
from omegaconf import OmegaConf, DictConfig

from ase import Atoms
from schnetpack import properties
from schnetpack import units as spk_units
from schnetpack.md import System, UniformInit, Simulator
from schnetpack.md.integrators import VelocityVerlet
from schnetpack.md.neighborlist_md import NeighborListMD
from schnetpack.transform import ASENeighborList
from schnetpack.md.calculators import SchNetPackCalculator
from schnetpack.md.simulation_hooks import LangevinThermostat, callback_hooks

from md_with_schnet.utils import set_data_prefix, load_xtb_dataset
from md_with_schnet.setup_logger import setup_logger

# TODO: update with the functions of inference_with_ase.py if needed
# Example command to run the script from within code directory:
"""
screen -dmS inference_xtb sh -c 'python -m md_with_schnet.neural_net.inference_with_schnetpack --trajectory_dir MOTOR_MD_XTB/T300_1 ; exec bash'
"""

logger = setup_logger("debug")

def parse_args() -> dict:
    """ Parse command-line arguments. 

    Returns:
        dict: Dictionary containing command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Script for predicting with trained model on XTB test data.")
    # paths setup
    parser.add_argument("--trajectory_dir", type=str, default="MOTOR_MD_XTB/T300_1", help="Directory containing the trajectory data generated by Turbomole (default: MOTOR_MD_XTB/T300_1)")
    return vars(parser.parse_args())

def set_simulation_hooks(cfg: DictConfig, md_workdir: str) -> list:
    """
    Set up the simulation hooks for the MD simulation.
    Args:
        cfg (DictConfig): Configuration object containing simulation parameters.
        md_workdir (str): Path to the working directory for the simulation.
    Returns:
        simulation_hooks (list): List of simulation hooks for the MD simulation.
    """
    # Initialize the thermostat and set it as a simulation hook
    #langevin = LangevinThermostat(cfg.md.system_temperature, cfg.md.time_constant)
    
    file_logger = set_file_logger(cfg, md_workdir)

    # Set the path to the checkpoint file and create checkpoint logger
    chk_file = os.path.join(md_workdir, 'simulation.chk')
    checkpoint = callback_hooks.Checkpoint(chk_file, every_n_steps=cfg.logger.checkpoint_every)

    # directory where tensorboard log will be stored to
    tensorboard_dir = os.path.join(md_workdir, 'logs')
    tensorboard_logger = callback_hooks.TensorBoardLogger(
        tensorboard_dir,
        cfg.logger.tensorboard_props, # properties to log
    )

    simulation_hooks = [
        # langevin,
        file_logger,
        checkpoint,
        tensorboard_logger,
    ]
    return simulation_hooks

def set_file_logger(cfg: DictConfig, md_workdir: str) -> callback_hooks.FileLogger:
    """ 
    Set up the file logger for the simulation.
    Args:
        cfg (DictConfig): Configuration object containing logging parameters.
        md_workdir (str): Path to the working directory for the simulation.
    Returns:
        file_logger (callback_hooks.FileLogger): The file logger for the simulation.
    """
    # Set up data streams to store positions, momenta and the energy
    data_streams = [
        callback_hooks.MoleculeStream(store_velocities=True),
        callback_hooks.PropertyStream(target_properties=[properties.energy]),
    ]

    # Create the file logger
    log_file = os.path.join(md_workdir, 'simulation_schnet.hdf5')
    file_logger = callback_hooks.FileLogger(
        log_file,
        cfg.logger.buffer_size,
        data_streams=data_streams,
        every_n_steps=cfg.logger.log_every,  # logging frequency
        precision=32,  # floating point precision used in hdf5 database
    )
    return file_logger

def main(trajectory_dir: str):
    ####################### 1) Compose the config ###########################
    with initialize(config_path="conf", job_name="inference"):
        cfg: DictConfig = compose(config_name="inference_config")
    logger.info(f"Loaded config:\n{OmegaConf.to_yaml(cfg)}")

    ####################### 2) Prepare Data and Paths #########################
    data_prefix = set_data_prefix()
    model_path = cfg.globals.model_path
    md_workdir = cfg.run.path
    logger.debug(f"data_prefix: {data_prefix}")
    logger.debug(f"Model path: {model_path}")
    logger.debug(f"MD workdir: {md_workdir}")

    split_file = os.path.join(data_prefix, "splits", trajectory_dir, "inner_splits_0.npz")
    if not os.path.exists(split_file):
        raise FileNotFoundError(f"Missing split file: {split_file}")
    path_to_db = os.path.join(data_prefix, trajectory_dir, "md_trajectory.db")
    logger.debug(f"Path to database: {path_to_db}")

    datamodule = load_xtb_dataset(
        db_path=path_to_db,
        num_workers=cfg.data.num_workers,
        batch_size=cfg.data.batch_size,
        split_file=split_file
    )


    ####################### 4) Prepare molecule ##############################
    structure = datamodule.test_dataset[0]
    atoms = Atoms(
        numbers=structure[spk.properties.Z],
        positions=structure[spk.properties.R],
    )

    ####################### 5) Setup MD system ##############################
    md_system = System()
    md_system.load_molecules(
        atoms,
        n_replicas=cfg.md.n_replicas,
        position_unit_input=cfg.model.units.length,
    )

    # Initial momenta
    md_initializer = UniformInit(
        cfg.md.system_temperature,
        remove_center_of_mass=True,
        remove_translation=True,
        remove_rotation=True,
    )
    md_initializer.initialize_system(md_system)

 
    ####################### 6) Setup calculators ##############################
    # initialize neighbor list for MD using the ASENeighborlist as basis
    md_neighborlist = NeighborListMD(
        cfg.model.neighborlist.cutoff,
        cfg.model.neighborlist.cutoff_shell,
        ASENeighborList,
    )
    md_calculator = SchNetPackCalculator(
        model_path,
        force_key=cfg.model.force_key,
        energy_unit=cfg.model.units.energy,
        position_unit=cfg.model.units.length,
        neighbor_list=md_neighborlist,
        energy_key=cfg.model.energy_key,
        required_properties=[], # additional properties extracted from the model
    )


    ######################## 7) Setup callbacks ##############################
    simulation_hooks = set_simulation_hooks(cfg, md_workdir)


    ####################### 8) Setup simulator ##############################
    device = "cuda" if torch.cuda.is_available() else "cpu"
    md_precision = getattr(torch, cfg.md.precision)
    # TODO use turbomole integrator
    # convert time step from atomic units to femto seconds
    time_step = cfg.md.time_step * 0.024188843265864
    logger.debug(f"Time step (in atomic units): {cfg.md.time_step}")
    logger.debug(f"Time step (in fs): {time_step}")

    md_integrator = VelocityVerlet(time_step)
    md_simulator = Simulator(md_system, md_integrator, md_calculator, simulation_hooks)
    md_simulator = md_simulator.to(md_precision)
    md_simulator = md_simulator.to(device)

    ####################### 9) Run simulation ##############################
    logger.info(f"Starting simulation with {cfg.md.n_steps} steps and saving to {md_workdir}")
    md_simulator.simulate(cfg.md.n_steps)
    logger.info("Simulation finished successfully.")


if __name__ == "__main__":
    args = parse_args()
    main(**args)