"""Start of the `setup` pipeline."""

import logging
import pandas as pd

from .config import Config
from .gt_from_hub import gt_from_hub

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup(config_path=None):
    """
    Main execution function for the epibench setup pipeline.
    """
    # validate config
    logger.info("Validating config...")
    config_object = Config(config_path=config_path, pipeline="setup")
    # can reference config info with:
    # .hub_path (Path)
    # .targets (list)
    # .dates (list of dates as strs)
    # .vintaging (bool)
    # .vintaging_method (str | None)
    # .output_path (Path)

    # go to hub, get gt data!
    logger.info("Fetching gt data from hub...")
    gt_data = gt_from_hub(
        hub_path=config_object.hub_path,
        targets=config_object.targets,
        dates=config_object.dates,
        vintaging=config_object.vintaging,
        vintaging_method=config_object.vintaging_method
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
        if gt_df is False: # Give warning if there wasn't a df returned
            logger.warning(f"NOTICE: No ground truth data found for specified targets ({config_object.targets}) for date {date}.")
            continue 
        else:
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
