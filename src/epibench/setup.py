"""Start of the `setup` pipeline."""

import logging
import pandas as pd

from .config import Config
from .gt_from_hub import gt_from_hub

from pathlib import Path
import json
import hashlib

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
    
    # hash the hub name and build output dirs to save its ground truth data
    hash = _get_hub_name_hash(config_object=config_object)
    output_base = config_object.output_path / hash

    try:
        output_base.mkdir(parents=True, exist_ok=False)
    except FileExistsError as e:
        raise FileExistsError(f"There is already a folder with hash {hash} at output directory {config_object.output_path}") from e
        # if this error gets thrown, it means there is already an output folder with that hash (we don't want to overwrite)
    gt_output_dir = output_base / "gt"
    gt_output_dir.mkdir(parents=False, exist_ok=False)
    # user/output/path/hash/gt/ directory established

    # save gt files to user/output/path/hash/gt/
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
            # make full output path of gt (user/output/path/hash/gt/YYYY-MM-DD/file.csv)
            gt_output_path = gt_output_date_folder / file_name
            gt_df.to_csv(gt_output_path, index=False)
            date_to_abs_gt_paths[date] = str(gt_output_path)

    # create challenges.csv at output_base (user/output/path/HASH-GOES-HERE/)
    challenges = pd.DataFrame(list(date_to_abs_gt_paths.items()), columns=["date", "absolute_path_to_gt"])
    challenges_output_path = output_base / "challenges.csv"
    challenges.to_csv(challenges_output_path, index=False)


def _get_hub_name_hash(config_object) -> str:
    """
    Return a SHA-256 hash of the hub official name or last folder name of hub_path.

    Args:
        config_object: Object containing a hub_path attribute.

    Returns:
        Hash of the hub name.
    """
    hub_path = Path(config_object.hub_path)

    # Default fallback
    hub_name = hub_path.name

    admin_json_path = hub_path / "hub-config" / "admin.json"

    if admin_json_path.is_file():
        try:
            with open(admin_json_path, "r", encoding="utf-8") as f:
                admin_data = json.load(f)

            repository = admin_data.get("repository", {})

            if isinstance(repository, dict):
                repo_name = repository.get("name")

                if isinstance(repo_name, str) and repo_name.strip():
                    hub_name = repo_name

        except (json.JSONDecodeError, OSError):
            pass

    # Hash the final selected name
    return hashlib.sha256(hub_name.encode("utf-8")).hexdigest()