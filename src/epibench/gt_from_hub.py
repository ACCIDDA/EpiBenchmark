"""write"""

import pandas as pd
import pygit2
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from hubdata import connect_target_data
from hubdata.create_target_data_schema import TargetType 

logger = logging.getLogger(__name__)

REPO_URLS = {
    "flusight": "https://github.com/cdcepi/FluSight-forecast-hub.git",
    "covid19": "https://github.com/CDCgov/covid19-forecast-hub.git",
    "rsv": "https://github.com/CDCgov/rsv-forecast-hub.git",
    "flu metrocast": "https://github.com/reichlab/flu-metrocast.git", 
}

HUB_TO_REPO_NAME = {
    "flusight": "FluSight-forecast-hub",
    "covid19": "covid19-forecast-hub",
    "rsv": "rsv-forecast-hub",
    "flu metrocast": "flu-metrocast"
}

def _vintaged_gt_fetch(hub_path: Path, targets: list, date: str, main_branch="main") -> pd.DataFrame: 
    """
    Fetch gt data at a specific date.

    This function is for vintaging=True runs, where it is important
    to fetch the gt data that was available at the given date. It does this
    by checking out `main` of the repo at a specified hub_path, pulling the
    oracle-output gt file, restoring the repo, and returning the file.
    """ 
    # convert str date to datetime date; set to EOD to capture any commits that happened that day
    date_obj = datetime.strptime(date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    # fetches from oracle-ouput.parquet/csv only (because it's in all 3 hubs) <- can change? ask joseph
    repo = pygit2.Repository(hub_path)

    commit = repo[repo.head.target]
    closest_commit = None
    while commit:
        if commit.commit_time <= date_obj.timestamp():
            closest_commit = commit
            break
        if commit.parents:
            commit = commit.parents[0]
        else:
            break

    if closest_commit:
        repo.checkout_tree(closest_commit.tree, strategy=pygit2.GIT_CHECKOUT_FORCE)
        repo.set_head(closest_commit.id)
        logger.info(
            f"Checked out commit on {date} (SHA: {closest_commit.id}, {commit.commit_time}) for repo {hub_path}"
        )
    else:
        raise ValueError(f"No commit found for date {date} in repo {hub_path} history")
    
    try:
        target_dir = hub_path / "target-data"
        parquet_file = target_dir / "oracle-output.parquet"
        csv_file = target_dir / "oracle-output.csv"
        if parquet_file.exists():
            df = pd.read_parquet(parquet_file) #TODO read in with the columns to have correct dtype (cast str)
        elif csv_file.exists():
            df = pd.read_csv(csv_file, low_memory=False) #TODO read in with the columns to have correct dtype (cast str)
        else:
            raise FileNotFoundError(f"Could not find ground truth file (oracle-output .csv or .parquet) in {target_dir}.")
        df = df[df['target'].isin(targets)]
        if df.empty:
            raise ValueError(f"Could not find targets {targets} in ground truth data")
    finally: # reset the repo to the head so that we can use it again
        branch_ref = "refs/heads/" + main_branch
        repo.checkout(branch_ref, strategy=pygit2.GIT_CHECKOUT_FORCE)



def _nonvintaged_gt_fetch(hub_path: Path, targets: list, dates: list) -> pd.DataFrame:
    """
    Fetch and filter gt data to contain MOST RECENT available
    data until the latest date (inclusive).

    This function is for vintaging=False runs, where users don't care
    to have gt data vintaged for each date (they just care about having
    gt values across all dates in the list).
    """

    # get the gt from the hub (accessing timeseries gt data)
    # non-vintaged gt data comes from timeseries file
    gt = connect_target_data(hub_path=hub_path, target_type=TargetType.TIME_SERIES).to_table().to_pandas()
    # keep only the target(s) we want; throw error if there are no target matches
    gt = gt[gt['target'].isin(targets)]
    if gt.empty:
        raise ValueError(f"Could not find target(s) {targets} in ground truth data.")
    # only keep most recent as_of values (best available data for every loc, target_end_date)
    gt = gt.sort_values(by='as_of', ascending=True)
    gt = gt.drop_duplicates(
        subset=["target_end_date", "location", "target"],
        keep="last",
        inplace=True
    )
    latest_date = max(dates)
    # cut off gt data at the latest date in `dates` param (inclusive)
    gt = gt[gt['target_end_date'] <= latest_date]
    if gt.empty:
        raise ValueError(f"Ground truth data does not contain any data for dates {dates} and target {targets}.")

    return gt, latest_date


def hub_clone_setup(hub: str) -> Path:
    """
    Fetch or pull the hub repo based on the hub.
    """
    
    # construct paths
    script_dir = Path(__file__).parent
    hub_parent_dir = script_dir / "hubs" / hub
    hub_path = hub_parent_dir / HUB_TO_REPO_NAME[hub]

    # if hub repo is already cloned, update it
    if hub_path.exists():
        logger.info(f"Updating existing hub repository: {hub_path.name}")
        subprocess.run(['git', 'pull'], cwd=hub_path, check=True)
        logger.info("Hub updated successfully.")

    # if hub repo is not already cloned, clone it
    else:
        logger.info(f"Cloning hub repository into {hub_parent_dir}")
        hub_parent_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'clone', REPO_URLS[hub]], cwd=hub_parent_dir, check=True)
        logger.info("Hub cloned successfully.")

    return hub_path 


def gt_from_hub(hub: str, targets: list, dates: list, vintaging: bool) -> dict:
    """
    Executes hub cloning/updating, ground truth data fetching 
    with or without vintaging, and return of that data.
    """

    # ensure clone existence, update if needed
    hub_path = hub_clone_setup(hub=hub)
    # establish return dict
    gt_dict = {}

    # if using vintaging, fetch iteratively
    if vintaging:
        for date in dates:
            gt_dict[str(date)] = _vintaged_gt_fetch(hub_path=hub_path, targets=targets, date=date)

    # if not using vintaging, fetch for latest date
    else:
        gt, latest_date = _nonvintaged_gt_fetch(
            hub_path=hub_path,
            targets=targets,
            dates=dates
        ) 
        gt_dict[latest_date] = gt 
    
    # return gt data dict (keyed by date)
    logger.info("Success ✅")
    return gt_dict

    