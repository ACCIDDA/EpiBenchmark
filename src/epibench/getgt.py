"""Start of the `getgt` pipeline."""

import argparse
import logging
import pandas as pd

from config import Config
from gt_from_hub import gt_from_hub

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def getgt():
    """
    Main execution function for the first EpiBench pipeline (fetching gt data from hub)
    """
    parser = argparse.ArgumentParser(description = 'Score models over specified time frame using a config.')
    parser.add_argument("--config-path",
                        type=str,
                        required=False,
                        help="Absolute path to your YAML configuration file.")
    args = parser.parse_args()

    # validate config
    logger.info("Validating config...")
    config_object = Config(config_path=args.config_path, pipeline='getgt')
    # can reference config info with:
    # .hub_path (Path)
    # .dates (list of dates as strs)
    # .vintaging (bool)
    # .output_path (Path)

    # -- TEMP ---
    print("\n\n\n\n")
    print(f"hub path: {config_object.hub_path} type {type(config_object.hub_path)}")
    print(f"dates: {config_object.dates} type {type(config_object.dates)}")
    print(f"vintaging: {config_object.vintaging} type {type(config_object.vintaging)}")
    print(f"output path: {config_object.output_path} type {type(config_object.output_path)}")
    print("\n\n\n\n")
    # --- END TEMP ---

    # go to hub, get gt data!
    logger.info("Fetching gt data from hub...")
    gt_data = gt_from_hub(
        hub_path=config_object.hub_path,
        dates=config_object.dates,
        vintaging=config_object.vintaging
    )
    # gt_data will be a dict where keys are dates and values are csvs of gt data
    # (unless vintaging is not being used, then the only key is just 'gt') 

    # build output dirs
    hash = "HASH-GOES-HERE" # TODO, hashing function create_hash()
    output_base = config_object.output_path / hash
    try:
        output_base.mkdir(parents=True, exist_ok=False)
    except FileExistsError as e:
        raise FileExistsError(f"There is already a folder with hash {hash} at output directory {config_object.output_path}") from e
        # if this error gets thrown, it means there is already an output folder with that hash (we don't want to overwrite)
    gt_output_dir = output_base / "gt"
    gt_output_dir.mkdir(parents=False, exist_ok=False)
    # user/output/path/HASH-GOES-HERE/gt/ directory established

    # save gt files to user/output/path/HASH-GOES-HERE/gt/
    date_to_abs_gt_paths = {}
    for date, gt_df in gt_data.items():
        file_name = f"{date.replace('-', '')}_gt.csv"
        # make user/output/path/HASH-GOES-HERE/gt/YYYY-MM-DD folder (one per date!)
        gt_output_date_folder = gt_output_dir / date 
        gt_output_date_folder.mkdir(parents=False, exist_ok=False)
        # make full output path of gt (user/output/path/HASH-GOES-HERE/gt/YYYY-MM-DD/file.csv)
        gt_output_path = gt_output_date_folder / file_name
        gt_df.to_csv(gt_output_path, index=False)
        date_to_abs_gt_paths[date] = str(gt_output_path)

    # create challenges.csv at output_base (user/output/path/HASH-GOES-HERE/)
    challenges = pd.DataFrame(list(date_to_abs_gt_paths.items()), columns=["date", "absolute_path_to_gt"])
    challenges_output_path = output_base / "challenges.csv"
    challenges.to_csv(challenges_output_path, index=False)


if __name__ == "__main__":
    getgt()

