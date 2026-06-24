"""
Functions associated with:
    - cloning/updating a hub (hub_clone_setup())
    - retrieving vintaged gt data via `git checkout` (_checkout_gt_fetch() exposed via gt_from_hub())
    - retrieving vintaged gt data via timeseries.csv "as_of" col (_asof_gt_fetch() exposed via gt_from_hub())
    - retrieving non-vintaged gt data via timeseries.csv "as_of" col (_asof_gt_fetch() exposed via gt_from_hub())

Ground truth data retreived via `git checkout` comes from oracle-output.csv/.parquet,
ground truth data retreived via "as_of" column comes from timeseries.csv.
"""

import pandas as pd
import pygit2
import logging
import subprocess
from urllib.parse import urlparse
from pathlib import Path
from datetime import datetime
from hubdata import connect_target_data
from hubdata.create_target_data_schema import TargetType 

logger = logging.getLogger(__name__)


def _checkout_gt_fetch(hub_path: Path, targets: list, date: str, main_branch="main") -> pd.DataFrame: 
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
        return df
    finally: # reset the repo to the head so that we can use it again
        branch_ref = "refs/heads/" + main_branch
        repo.checkout(branch_ref, strategy=pygit2.GIT_CHECKOUT_FORCE)



def _asof_gt_fetch(
        hub_path: Path, 
        targets: list, 
        date_s: list | str
    ) -> tuple[pd.DataFrame | bool, str]:
    """
    Fetch and filter gt data from a hub using the 'as_of'
    column of a timeseries.csv gt data file.

    This function is for vintaging=False runs, where users don't care
    to have gt data vintaged for each date, or for vintaging=True with
    vintaging_method="as_of" runs where users want vintaged data according
    to the as_of column.

    Args:
        hub_path: Path to a local clone of a hub/hub repo.
        targets: List of targets to get gt data for.
        date_s: List of dates or single date (to match with as_of col).

    Returns:
        Tuple with pd.DataFrame of gt data and a date that describes the gt 
        data (either the latest date included or the only date fetched).
    """

    # multiple dates (fetch to cover a range). use case: non-vintaged gt fetch
    if isinstance(date_s, list): 
        # find max date, convert to date obj 
        latest_date_str = max(date_s)
        latest_date_obj = datetime.strptime(latest_date_str, "%Y-%m-%d").date()
        # get the gt from the hub (accessing timeseries gt data)
        gt = connect_target_data(hub_path=hub_path, target_type=TargetType.TIME_SERIES).to_table().to_pandas()
        # keep only the target(s) we want; throw error if there are no target matches
        gt = gt[gt['target'].isin(targets)]
        if gt.empty:
            raise ValueError(f"Could not find target(s) {targets} in ground truth data.")
        # only keep most recent as_of values (best available data for every loc, target_end_date)
        gt = gt.sort_values(by='as_of', ascending=True)
        gt = gt.drop_duplicates(
            subset=["target_end_date", "location", "target"],
            keep="last"
        )
        # cut off gt data at the latest date in `dates` param (inclusive)
        gt = gt[gt['target_end_date'] <= latest_date_obj]
        if gt.empty:
            raise ValueError(f"Ground truth data does not contain any data for dates {date_s} and target {targets}.")

        return gt, latest_date_str
    
    # singe date fetch. use case: vintaged gt fetch w/ vintaging_method: "as_of"
    elif isinstance(date_s, str): 
        date_s_obj = datetime.strptime(date_s, "%Y-%m-%d").date()
        gt = connect_target_data(hub_path=hub_path, target_type=TargetType.TIME_SERIES).to_table().to_pandas()
        # only keep target(s) we want; throw WARNING and proceed to next date if there are none
        gt = gt[gt['target'].isin(targets)]
        if gt.empty:
            logger.warning(
                f"Could not find target(s) {targets} in ground truth data for date {date_s}. "
                "Proceeding to next date."
            )
            return False, date_s # returning no gt data, proceeding
        # only keep things vintaged to the date we specified
        # flexible matching to as_of (closest without going over)
        valid_vintages = gt[gt['as_of'] <= date_s_obj]
        if valid_vintages.empty:
            raise ValueError(
                f"Could find no groudn truth data on or before {date_s} included in your span of dates. "
                "Please ensure your dates do not extend outside of hub existence or into the future."
            )
        closest_date = valid_vintages['as_of'].max()
        gt = valid_vintages[valid_vintages['as_of'] == closest_date]
        # filter the target_end_dates as well
        gt = gt[gt['target_end_date'] <= date_s_obj]
        # if gt.empty:
            # possible check to have, but this should never trigger because 
            # target_end_date should remain in pseudo synchronicity w/ as_of
        return gt, date_s


def hub_clone_setup(hub_url: str) -> Path:
    """
    Clone the hub repo given a GitHub URL, or pull if a clone already exists.
    """
    # get name of repo
    parsed_path = urlparse(hub_url).path
    repo_name = parsed_path.strip("/").split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    # get project root direcotry
    project_root = Path(__file__).resolve().parent[2]
    # create hub folder under project root directory
    hubs_dir = project_root / "hubs"
    # create repo folder under hub folder
    hub_path = hubs_dir / repo_name

    # clone if it hasn't been yet, otherwise pull to update
    if hub_path.exists() and hub_path.is_dir():
        logger.info(f"Updating existing hub repository: {repo_name}")
        subprocess.run(['git', 'pull'], cwd=hub_path, check=True)
        logger.info("Hub updated successfully.")
    else:
        logger.info(f"Cloning hub repository into {hubs_dir}")
        hubs_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'clone', hub_url], cwd=hubs_dir, check=True)
        logger.info("Hub cloned successfully.")

    return hub_path 


def gt_from_hub(
        hub_path: Path, 
        targets: list, 
        dates: list, 
        vintaging: bool,
        vintaging_method: str | None
    ) -> dict:
    """
    Executes hub cloning/updating, ground truth data fetching 
    with or without vintaging, and return of that data.
    """
    # establish return dict
    gt_dict = {}

    # if using vintaging, fetch iteratively
    if vintaging:
        for date in dates:
            if vintaging_method == 'checkout':
                gt_dict[str(date)] = _checkout_gt_fetch(hub_path=hub_path, targets=targets, date=date)
            elif vintaging_method == 'as_of':
                gt, _ = _asof_gt_fetch(hub_path=hub_path, targets=targets, date_s=date)
                gt_dict[str(date)] = gt 

    # if not using vintaging, fetch for latest date
    else:
        gt, latest_date = _asof_gt_fetch(
            hub_path=hub_path,
            targets=targets,
            date_s=dates
        ) 
        gt_dict[latest_date] = gt 
    
    # return gt data dict (keyed by date)
    logger.info("Success ✅")
    return gt_dict

    
