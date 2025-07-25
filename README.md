# Molecular Dynamics with Neural Networks

This project was part of a six-month, part-time research assistant position under the supervision of Professor Enrico Tapavicza. The main goal is to speed up the prediction of forces and the energy of a second-generation Feringa-type molecular nanomotor. In our case this is 9-(2’-methyl-2’,3’-dihydro-1’H-cyclopenta[a]naphthalen-1’-ylidene)-9H-xanthene (CPNX). 

## Outline

1. [Project Structure](#project-structure)
2. [Installation](#installation)
3. [Workflow](#workflow)
4. [Contributing](#contributing)
5. [License](#license)

## Project Structure

The "md_with_schnet" directory contains everything of the project, as we have only worked with [SchNetPack](https://github.com/atomistic-machine-learning/schnetpack) so far. The "deprecated" directory contains every outdated piece of code, that at some point will be removed from this project.


## Installation

Once you have cloned this project, you can use the environment.yaml file to build the conda environment needed to execute the project code. The needed commands are as follows:


```bash
git clone git@github.com:FerdinandToelkes/whk.git
conda env create -f path/to/environment.yml
conda activate schnet
```

## Workflow

Each script should include an example of how to execute it at the top.

### preprocessing

- All python scripts are to be executed from the root directory of the project, i.e. the directory containing the "md_with_schnet" directory.
- The "target_dir" as well as the "trajectory_dir" parameters have to be set relative to the data directory (see also set_data_prefix within utils.py). In my case, we could have target_dir = MOTOR_MD_XTB/T300_1
- Obtain gradients, positions and velocities from mdlog.i files with the extract.py script:
```bash
python -m md_with_schnet.preprocessing.extract \
    --property gradients \
    --target_dir path/to/dir/with/mdlog.i/files
```
- Obtain energies from mdlog.i files with Turbomole by executing directly in the directory with the mdlog.i files:
```bash
log2egy > energies.txt
```
- Transform the extracted properties into a .db file (which is the format used within SchNetPack) by employing the prepare_xtb_in_atomic_units.py or the prepare_xtb_ang_kcal_mol.py  script
```bash
python -m md_with_schnet.preprocessing.prepare_xtb_data \
    --trajectory_dir path/to/dir/with/mdlog.i/files \
    --num_atoms 48 --position_unit angstrom \
    --energy_unit kcal/mol --time_unit fs
```
- Define how the data later should be splitted into training, validation and test data via the create_splits.py script:
```bash
python -m md_with_schnet.preprocessing.create_splits \
    --trajectory_dir path/to/dir/with/mdlog.i/files \
    --units angstrom_kcal_per_mol_fs 
```
- If needed, compute the mean and standard deviation of the various properties in the training set via the compute_means_and_stds.py script:
```bash
python -m md_with_schnet.preprocessing.compute_means_and_stds \
    --trajectory_dir path/to/dir/with/mdlog.i/files \
    --num_atoms=48 --units angstrom_kcal_per_mol_fs
```
Note that paths need to be updated depending on the local setup especially of the data. 

### neural_net

- Use train.py to train a neural network via SchNetPack (adjust parameters via the command line or the .yml config file if necessary)
```bash
screen -dmS xtb_train sh -c 'python -m md_with_schnet.neural_net.train \ 
    --trajectory_dir path/to/dir/with/mdlog.i/files --epochs 1000  \ 
    --batch_size 100 --learning_rate 0.0001 --seed 42 \
    --config_name train_config_default_transforms 
    --units angstrom_kcal_per_mol_fs; exec bash'
```
- Use get_test_metrics.py to predict the energies, forces and gradients of the test set with the trained model
```bash
python -m md_with_schnet.neural_net.get_test_metrics \
    --model_dir MOTOR_MD_XTB/T300_1/epochs_1000_bs_100_lr_0.0001_seed_42
```
- Run inference_with_ase.py to generate a MD trajectory starting from a configuration within the test dataset
```bash
screen -dmS inference_xtb sh -c 'python -m md_with_schnet.neural_net.inference_with_ase \
    --model_dir MOTOR_MD_XTB/T300_1/epochs_1000_bs_100_lr_0.0001_seed_42 \
    --units angstrom_kcal_per_mol_fs --md_steps 100 --time_step 0.5 ; exec bash'
```
- Execute ~~order 66~~ the plot_interactive_md_ase_sim.py script in order to gain an overview of the various energies from the two trajectories as well as their correlation 
```bash
python -m md_with_schnet.neural_net.plot_interactive_md_ase_sim \
    --model_dir MOTOR_MD_XTB/T300_1/epochs_1000_bs_100_lr_0.0001_seed_42 \
    --simulation_name  md_sim_steps_5000_time_step_1.0_seed_42 \
    --n_samples 5000 --units angstrom_kcal_per_mol_fs
```

## Data Overview

The dataset used for training the neural network consists of five replica exchange molecular dynamics (REMD) simulations performed with the xTB software. The simulations were carried out on the CPNX nanomotor which consists of 48 atoms, and the data includes information about atomic positions, energies, forces and velocities. Different dihedral angles were defined in order to cluster the sampled structures into the following four confirmations: "syn-M", "anti-M", "syn-P" and "anti-P". See the [paper](https://pubs.rsc.org/en/content/articlepdf/2025/cp/d5cp01063b) by Lucia-Tamudo et al. for more details on the underlying data. The evolution of the dihedral angles for one of the simulations can be viewed [here](https://FerdinandToelkes.github.io/whk/dihedral_angles_MOTOR_MD_XTB_T300_1.html).

## Results

Here is a quick overview of results for training a neural network on the MOTOR_MD_XTB/T300_1 dataset. We used the trained model to run a MD and the plots show a comparison between the model's prediction for the energies with predictions made by xTB that can be viewed [here](https://FerdinandToelkes.github.io/whk/angstrom_kcal_per_mol_fs/MOTOR_MD_XTB/T300_1/epochs_1000_bs_100_lr_0.0001_seed_42/md_sim_steps_5000_time_step_1.0_seed_42/interactive_properties_plot.html) and the corresponding rolling correlation between the energies, that is displayed in [this plot](https://FerdinandToelkes.github.io/whk/angstrom_kcal_per_mol_fs/MOTOR_MD_XTB/T300_1/epochs_1000_bs_100_lr_0.0001_seed_42/md_sim_steps_5000_time_step_1.0_seed_42/interactive_rolling_corr_plot.html)
 

## Contributing

If you would like to contribute to the project, please open an issue or a pull request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

