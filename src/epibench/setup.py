"""Start of the `setup` pipeline."""

import logging
import pandas as pd
from pathlib import Path
import hashlib
import json

from .config import Config
from .setup_ground_truth import gt_from_hub

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
    # .challenge_name(str)
    # .targets (list)
    # .dates (list of dates as strs)
    # .vintaging (bool)
    # .vintaging_method (str | None)
    # .vintaging_offset (int)
    # .output_path (Path)

    # go to hub, get gt data!
    logger.info("Fetching gt data from hub...")
    gt_data = gt_from_hub(
        hub_path=config_object.hub_path,
        targets=config_object.targets,
        reference_dates=config_object.dates,
        data_cutoff_dates=config_object.gt_cutoff_dates,
        vintaging=config_object.vintaging,
        vintaging_method=config_object.vintaging_method
    )
    # gt_data will be a dict where keys are dates and values are csvs of gt data

    # build output dirs
    challenge_id = _build_challenge_id(config_object=config_object)
    output_base = config_object.output_path / challenge_id
    
    try:
        output_base.mkdir(parents=True, exist_ok=False)
    except FileExistsError as e:
        raise FileExistsError(f"There is already a folder with challenge_id {challenge_id} at output directory {config_object.output_path}") from e
        # if this error gets thrown, it means there is already an output folder with that challenge_id (we don't want to overwrite)
    gt_output_dir = output_base / "gt"
    gt_output_dir.mkdir(parents=False, exist_ok=False)
    # user/output/path/challenge_id/gt/ directory established

    # save gt files to user/output/path/challenge_id/gt/
    date_to_abs_gt_paths = {}
    for date, gt_df in gt_data.items():
        if gt_df is False: # Give warning if there wasn't a df returned
            logger.warning(f"NOTICE: No ground truth data found for specified targets ({config_object.targets}) for date {date}.")
            continue 
        else:
            file_name = f"{date.replace('-', '')}_gt.csv"
            # make user/output/path/challenge_id/gt/YYYY-MM-DD folder (one per date!)
            gt_output_date_folder = gt_output_dir / date 
            gt_output_date_folder.mkdir(parents=False, exist_ok=False)
            # make full output path of gt (user/output/path/challenge_id/gt/YYYY-MM-DD/file.csv)
            gt_output_path = gt_output_date_folder / file_name
            gt_df.to_csv(gt_output_path, index=False)
            date_to_abs_gt_paths[date] = str(gt_output_path)

    # create task_list.csv at output_base (user/output/path/challenge_id/)
    task_list = pd.DataFrame(list(date_to_abs_gt_paths.items()), columns=["date", "absolute_path_to_gt"])
    task_list_output_path = output_base / "task_list.csv"
    task_list.to_csv(task_list_output_path, index=False)


def _build_challenge_id(config_object: Config) -> str:
    """
    Construct a challenge_id by using user defined challenge name
    and the hash generated from:
      - hub official name
      - targets
      - dates
      - vintaging
      - vintaging_method
      - vintaging_offset

    Returns:
        challenge_name_hash (str)
    """
    local_hub_path = Path(config_object.hub_path)
    hub_name = local_hub_path.name

    admin_json_path = local_hub_path / "hub-config" / "admin.json"

    if admin_json_path.is_file():
        try:
            with open(admin_json_path, "r", encoding="utf-8") as f:
                admin_data = json.load(f)

            repository = admin_data.get("repository", {})
            repo_name = repository.get("name")

            if isinstance(repo_name, str) and repo_name.strip():
                hub_name = repo_name

        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                "Unable to read %s (%s). Using folder name '%s'.",
                admin_json_path,
                e,
                hub_name,
            )

    
    # Build a deterministic object to hash
    hash_input = {
        "hub_name": hub_name,
        "targets": config_object.targets,
        "dates": config_object.dates,
        "vintaging": config_object.vintaging,
        "vintaging_method": config_object.vintaging_method,
        "vintaging_offset": config_object.vintaging_offset,
    }

    # Convert to a JSON string
    hash_string = json.dumps(hash_input, sort_keys=True)

    # hash the string and keep the first 10 hex characters
    hash_value = hashlib.sha256(hash_string.encode("utf-8")).hexdigest()
    short_hash = hash_value[:10]

    return f"{config_object.challenge_name}_{short_hash}"
