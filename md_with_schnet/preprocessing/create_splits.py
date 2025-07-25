import argparse
import os
import numpy as np

from md_with_schnet.setup_logger import setup_logger
from md_with_schnet.utils import load_xtb_dataset_without_given_splits, set_data_prefix

logger = setup_logger(logging_level_str="debug")

# Script to generate splits for an inner k-fold cross-validation and save them in a ASE compatible format.
# Example command to run the script from within code directory:
"""
python -m md_with_schnet.preprocessing.create_splits --trajectory_dir MOTOR_MD_XTB/T300_1 --units angstrom_kcal_per_mol_fs
"""


def parse_args() -> dict:
    """ 
    Parse command-line arguments. 
    Returns:
        dict: Dictionary containing command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Script for generating splits for cross validation.")
    parser.add_argument("--trajectory_dir", type=str, default="MOTOR_MD_XTB/T300_1", help="Directory containing the trajectory data generated by Turbomole (default: MOTOR_MD_XTB/T300_1)")
    parser.add_argument("--units", type=str, default="angstrom_kcal_per_mol_fs", choices=["angstrom_kcal_per_mol_fs", "angstrom_ev_fs", "bohr_hartree_aut"], help="Units for the input data (default: angstrom_kcal_per_mol_fs).")
    return vars(parser.parse_args())

def check_overlap_inner_split(train_indices, val_indices, test_indices):
    """
    Check if there is any overlap between the train, validation, and test indices.
    Args:
        train_indices (list): List of train indices.
        val_indices (list): List of validation indices.
        test_indices (list): List of test indices.
    Raises:
        ValueError: If there is an overlap between the indices.
    """
    if len(set(train_indices) & set(val_indices)) > 0:
        raise ValueError("Overlap between train and val indices!")
    if len(set(train_indices) & set(test_indices)) > 0:
        raise ValueError("Overlap between train and test indices!")
    if len(set(val_indices) & set(test_indices)) > 0:
        raise ValueError("Overlap between val and test indices!")
    logger.info("No overlap between train, val and test indices!")
    
def check_overlap_outer_split(train_indices, test_indices):
    """
    Check if there is any overlap between the train and test indices.
    Args:
        train_indices (list): List of train indices.
        test_indices (list): List of test indices.
    Raises:
        ValueError: If there is an overlap between the indices.
    """
    if len(set(train_indices) & set(test_indices)) > 0:
        raise ValueError("Overlap between train and test indices!")
    logger.info("No overlap between train and test indices!")
    
def main(trajectory_dir: str, units: str):
    # setup
    data_prefix = set_data_prefix()
    splits_dir = os.path.join(data_prefix, 'splits', trajectory_dir)
    os.makedirs(splits_dir, exist_ok=True)
    path_to_data = os.path.join(data_prefix, trajectory_dir, f'md_trajectory_{units}.db')
    np.random.seed(42)

    # load XTB dataset
    xtb = load_xtb_dataset_without_given_splits(path_to_data, batch_size=10)
    total_length = len(xtb.dataset)
    logger.info(f"Total length of dataset: {total_length}")

    # create outer split - 80% train, 20% test
    outer_train_split = int(total_length * 0.8)
    outer_train_indices = list(range(outer_train_split))
    outer_test_indices = list(range(outer_train_split, total_length))
    logger.debug(f"Outer train indices[:10]: {outer_train_indices[:10]}")
    logger.debug(f"Outer test indices[:10]: {outer_test_indices[:10]}")

    # save outer splits as npz file
    outer_splits = {
        "train": outer_train_indices,
        "test": outer_test_indices
    }
    outer_splits_path = os.path.join(splits_dir, "outer_splits.npz")
    # check if they overlap
    check_overlap_outer_split(outer_train_indices, outer_test_indices)

    if os.path.exists(outer_splits_path):
        logger.error(f"Outer splits already exist at {outer_splits_path}. Please remove it to create new splits.")
        raise FileExistsError(f"Outer splits already exist at {outer_splits_path}. Please remove it to create new splits.")
    np.savez(outer_splits_path, **outer_splits)
    logger.info(f"Saved outer splits to: {outer_splits_path}")

    # create inner splits - 5 fold 80% train, 20% validation
    k_fold = 5 
    inner_train_split = int(outer_train_split*0.8) 
    inner_test_split = outer_train_split - inner_train_split
    for k in range(k_fold):  
        inner_val_indices = outer_train_indices[k*inner_test_split : (k+1)*inner_test_split]
        inner_train_indices = [i for i in outer_train_indices if i not in inner_val_indices]
        # save train, val and test indices as npz file
        inner_splits = {
            "train_idx": inner_train_indices, # naming important for ASE
            "val_idx": inner_val_indices,
            "test_idx": outer_test_indices
        }

        # check if they overlap
        check_overlap_inner_split(inner_train_indices, inner_val_indices, outer_test_indices)

        inner_splits_path = os.path.join(splits_dir, f"inner_splits_{k}.npz")
        np.savez(inner_splits_path, **inner_splits)
        logger.info(f"Saved inner splits from fold {k} to: {inner_splits_path}")
    

        

if __name__=="__main__":
    args = parse_args()
    main(**args)