"""write"""

import pandas as pd
import pygit2
import logging
from pathlib import Path
from datetime import datetime
from hubdata import connect_target_data
from hubdata.create_target_data_schema import TargetType # maybe don't need this one?

logger = logging.getLogger(__name__)


def _vintaged_gt_fetch(hub_path: Path, date, main_branch="main") -> pd.DataFrame: #TODO, what happens if repo isn't up to date and doesn't have commits from specified dates or dates are in the future? 
    """write""" 
    # convert str date to datetime date; set to EOD to capture any commits that happened that day
    date_obj = datetime.strptime(date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    # fetches from oracle-ouput.parquet/csv only (because it's in all 3 hubs) <- can change? ask joseph
    repo = pygit2.Repository(hub_path)

    closest_commit = None
    for commit in repo.walk(repo.head.target, pygit2.GIT_SORT_TIME):
        if commit.commit_time <= date_obj.timestamp():
            closest_commit = commit
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
            return pd.read_parquet(parquet_file)
        elif csv_file.exists():
            return pd.read_csv(csv_file, low_memory=False)
        else:
            raise FileNotFoundError(f"Could not find ground truth file (oracle-output .csv or .parquet) in {target_dir}.")
    finally: # reset the repo to the head so that we can use it again
        branch_ref = "refs/heads/" + main_branch
        repo.checkout(branch_ref, strategy=pygit2.GIT_CHECKOUT_FORCE)



def _nonvintaged_gt_fetch(hub_path: Path, dates: list) -> pd.DataFrame:
    """
    Fetch and filter gt data to contain MOST RECENT available
    data until the latest date (inclusive).

    This function is for vintaging=False runs, where users don't care
    to have gt data vintaged for each date (they just care about having
    gt values across all dates in the list).
    """

    # get the gt from the hub (accessing timeseries gt data)
    gt = connect_target_data(hub_path=hub_path, target_type=TargetType.TIME_SERIES).to_table().to_pandas()
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

    return gt, latest_date


def gt_from_hub(hub_path: Path, dates: list, vintaging: bool) -> dict:
    """write"""

    gt_dict = {}


    if vintaging:
        for date in dates:
            gt_dict[str(date)] = _vintaged_gt_fetch(hub_path=hub_path, date=date)

    else:
        gt, latest_date = _nonvintaged_gt_fetch(
            hub_path=hub_path,
            dates=dates
        ) 
        gt_dict[latest_date] = gt 
    

    logger.info("Success ✅")
    return gt_dict

    