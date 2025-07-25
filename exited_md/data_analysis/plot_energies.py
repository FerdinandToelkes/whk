import argparse
import os
import numpy as np

# for interactive plotting
import plotly.graph_objects as go
# ensure that no conflict with jupyter package (ipykernel) occurs
import plotly.io as pio
pio.renderers.default = 'browser'

from md_with_schnet.setup_logger import setup_logger
from md_with_schnet.utils import set_data_prefix
from exited_md.preprocessing.extract_energies import read_ex_energies_file, convert_ex_energies_to_absolute


logger = setup_logger(logging_level_str="debug")

# Example command to run the script from within code directory:
"""
python3 -m exited_md.data_analysis.plot_energies --trajectory_dir PREPARE_12/GEO_100000/test
"""


def parse_args() -> dict:
    """ 
    Parse command-line arguments. 
    Returns:
        dict: Dictionary containing command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Plotting script for XTB datasets")
    parser.add_argument("--trajectory_dir", type=str, default="PREPARE_12/GEO_100000/test", help="Directory containing the trajectory data generated by Turbomole (default: PREPARE_12/GEO_100000/test)")
    parser.add_argument("--nr_of_configs", type=int, default=-1, help="Number of configurations to use (default: -1). If negative, all available configurations will be used.")
    return vars(parser.parse_args())




def create_interactive_energies_plot(energies: dict, index: np.ndarray, plot_dir: str, trajectory_dir: str):
    """
    Create an interactive plot with dropdown buttons to select different properties.
    Args:
        properties (dict): Dictionary containing the properties to plot.
        index (np.ndarray): Array of index values of the configurations.
        plot_dir (str): Directory to save the plot.
        trajectory_dir (str): Directory containing the trajectory data for the plot title.
    """
    #### Build the figure ##################################################
    fig = go.Figure()

    all_props = list(energies.keys())
    for i, prop_name in enumerate(all_props):
        y = energies[prop_name]

        # Add the trace:
        label = prop_name.replace("_", " ").capitalize()
        fig.add_trace(
            go.Scatter(
                x=index,
                y=y,
                mode="lines",
                name=f"{label}",
            )
        )
    

    #### Initial layout ##################################################
    fig.update_layout(
        updatemenus=[
            dict(
                active=0,
                x=0.0,
                y=1.15,
                xanchor="left",
                yanchor="top",
                direction="down",
                pad={"r": 10, "t": 10},
                showactive=True,
            )
        ],
        title={
            "text": f"Energies over Time for {trajectory_dir}",
            "x": 0.5,
            "xanchor": "center",
        },
        xaxis_title="Configuration Index",
        yaxis_title="Energy [Hartree]",
    )
    # save the figure to a file
    traj_dir = trajectory_dir.replace("/", "_")
    fig.write_html(f"{plot_dir}/energies_{traj_dir}.html")
    logger.info(f"Plot saved to {plot_dir}/energies_{traj_dir}.html")


def main(trajectory_dir: str, nr_of_configs: int):
    # setup
    plot_dir = os.path.expanduser('~/whk/code/exited_md/data_analysis/plots')
    os.makedirs(plot_dir, exist_ok=True)
    data_prefix = os.path.join(set_data_prefix(), trajectory_dir)
    
    path_to_energies = os.path.join(data_prefix, 'energies.txt')
    if not os.path.exists(path_to_energies):
        raise FileNotFoundError(f"File {path_to_energies} does not exist. Please use log2egy > energies.txt to create it.")
    energies = np.loadtxt(path_to_energies, usecols=(0, 1, 2, 3, 5)) # t, E_kin, E_tot, E_pot, T
    logger.info(f"Loaded energies from {path_to_energies}, shape: {energies.shape}")
    logger.debug(f"First 5 rows of energies:\n{energies[:5]}")

    path_to_ex_energies = os.path.join(data_prefix, 'ex_energies')
    rel_ex_energies = read_ex_energies_file(path_to_ex_energies) # S0, S1-S0, S2-S0
    ex_energies = convert_ex_energies_to_absolute(rel_ex_energies)  # S0, S1, S2
    logger.info(f"Loaded potential energies from {path_to_ex_energies}, shape: {ex_energies.shape}")

    if nr_of_configs > energies.shape[0]:
        logger.warning(f"Requested {nr_of_configs} configurations, but only {energies.shape[0]} are available. Using all available configurations.")
        nr_of_configs = energies.shape[0]
    elif nr_of_configs < 0:
        logger.info(f"Using all available configurations.")
        nr_of_configs = energies.shape[0]
    energies = energies[:nr_of_configs]

    energies_dict = {
        "E_kin": energies[:, 1],
        "E_tot": energies[:, 2],
        "E_pot active state": energies[:, 3],
        "T": energies[:, 4],
        "S0": ex_energies[:, 0],
        "S1": ex_energies[:, 1],
        "S2": ex_energies[:, 2],
    }
    index = np.arange(nr_of_configs) 
    create_interactive_energies_plot(energies_dict, index, plot_dir, trajectory_dir)


if __name__=="__main__":
    args = parse_args()
    main(**args)