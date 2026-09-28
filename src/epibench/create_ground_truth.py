"""Retrieve and standardize ground truth for the ``epibench create`` pipeline."""

import importlib
import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pandas as pd
import pygit2

from .hub_date_utils import create_season_start


logger = logging.getLogger(__name__)
hub_target_data_schema_module = importlib.import_module("hubdata.create_target_data_schema")

AS_OF_COLUMN = "as_of"


@contextmanager
def _suppress_missing_target_data_schema_warning(enabled: bool):
    """Suppress hubdata's missing target-data.json fallback warning.

    This compatibility helper is also used by the scoring pipeline.
    """
    if not enabled:
        yield
        return

    original_warn = hub_target_data_schema_module.logger.warn

    def _filtered_warn(event=None, *args, **kwargs):
        if event == "target-data.json not found. using inferred schema from data":
            return None
        return original_warn(event, *args, **kwargs)

    hub_target_data_schema_module.logger.warn = _filtered_warn
    try:
        yield
    finally:
        hub_target_data_schema_module.logger.warn = original_warn


def _ground_truth_path(hub_path: Path, gt_file: str) -> Path:
    """Resolve a user-configured ground truth path within the hub repository."""
    relative_path = Path(gt_file)
    if relative_path.is_absolute():
        raise ValueError("`ground_truth_file` must be a path relative to the hub repository root.")

    resolved_hub_path = hub_path.resolve()
    resolved_gt_path = (resolved_hub_path / relative_path).resolve()
    try:
        resolved_gt_path.relative_to(resolved_hub_path)
    except ValueError as error:
        raise ValueError("`ground_truth_file` must not resolve outside the hub repository.") from error

    return resolved_gt_path


def _read_ground_truth_file(hub_path: Path, gt_file: str) -> pd.DataFrame:
    """Read the configured CSV or Parquet ground truth file from a hub checkout."""
    ground_truth_path = _ground_truth_path(hub_path, gt_file)
    if not ground_truth_path.is_file():
        raise FileNotFoundError(
            f"Could not find configured ground truth file {gt_file!r} in hub repository {hub_path}."
        )

    if ground_truth_path.suffix.lower() == ".parquet":
        return pd.read_parquet(ground_truth_path)
    if ground_truth_path.suffix.lower() == ".csv":
        return pd.read_csv(ground_truth_path, low_memory=False)

    raise ValueError("`ground_truth_file` must point to a .csv or .parquet file.")


def _validate_columns(df: pd.DataFrame, required_columns: list[str]) -> None:
    """Require all columns needed to construct the create-pipeline output."""
    missing_columns = set(required_columns).difference(df.columns)
    if missing_columns:
        raise ValueError(
            "Ground truth data is missing required column(s): "
            f"{', '.join(sorted(missing_columns))}."
        )


def _filter_target_if_present(df: pd.DataFrame, target: str) -> tuple[pd.DataFrame, bool]:
    """Filter the requested target when the source data supplies a target column."""
    if "target" not in df.columns:
        return df, False

    filtered_df = df[df["target"] == target].copy()
    if filtered_df.empty:
        raise ValueError(f"Could not find target {target!r} in ground truth data.")
    return filtered_df, True


def _resolve_duplicates(
    df: pd.DataFrame,
    vintage_date: str,
    gt_file: str,
) -> pd.DataFrame:
    """Resolve duplicates across the complete source schema when an as-of date is available."""
    if AS_OF_COLUMN not in df.columns:
        duplicate_rows = df.loc[df.duplicated(keep=False)]
        if duplicate_rows.empty:
            return df

        duplicates = duplicate_rows.to_dict(orient="records")
        raise ValueError(
            f"DUPLICATES DETECTED: {duplicates}\n"
            "COULD NOT RESOLVE DUPLICATES BECAUSE NO `as_of` column is present in "
            f"{gt_file}."
        )

    as_of_values = pd.to_datetime(df[AS_OF_COLUMN], errors="coerce")
    if as_of_values.isna().any():
        raise ValueError("Ground truth data contains missing or invalid `as_of` values.")

    cutoff_timestamp = pd.Timestamp(vintage_date)
    available_df = df.assign(_as_of_sort_value=as_of_values)
    available_df = available_df[available_df["_as_of_sort_value"] <= cutoff_timestamp]
    if available_df.empty:
        raise ValueError(
            f"Ground truth data does not contain an `as_of` vintage on or before {vintage_date}."
        )

    duplicate_key_columns = [column for column in df.columns if column != AS_OF_COLUMN]

    # Stable sorting makes an exact as_of tie resolve to the later source-file row.
    return (
        available_df.sort_values(by="_as_of_sort_value", kind="stable")
        .drop_duplicates(
            subset=duplicate_key_columns,
            keep="last",
        )
        .drop(columns="_as_of_sort_value")
    )


def _filter_to_cutoff_target_end_date(
    df: pd.DataFrame, cutoff_date: str, date_column: str
) -> pd.DataFrame:
    """Keep observations whose target end date is no later than the requested cutoff."""
    target_end_dates = pd.to_datetime(df[date_column], errors="coerce")
    return df.loc[target_end_dates <= pd.Timestamp(cutoff_date)].copy()


def _keep_output_columns(
    df: pd.DataFrame,
    date_column: str,
    location_column: str,
    observed_column: str,
    target: str,
) -> pd.DataFrame:
    """Return standardized create-pipeline columns, including ``target`` and ``observed``."""
    standardized_df = (
        df.loc[:, [date_column, location_column, observed_column]]
        .rename(
            columns={
                date_column: "target_end_date",
                location_column: "location",
                observed_column: "observed",
            }
        )
        .copy()
    )
    standardized_df["target"] = df["target"] if "target" in df.columns else target
    return standardized_df.loc[:, ["target_end_date", "location", "target", "observed"]]


def _filter_to_reference_season(df: pd.DataFrame, reference_date: str) -> pd.DataFrame:
    """Keep fetched observations from July 1 through the task's reference date."""
    reference_day = datetime.strptime(reference_date, "%Y-%m-%d").date()
    target_end_dates = pd.to_datetime(df["target_end_date"], errors="coerce").dt.date
    return df.loc[
        (target_end_dates >= create_season_start(reference_day))
        & (target_end_dates <= reference_day)
    ].copy()


def _checkout_gt_fetch(
    hub_path: Path,
    gt_file: str,
    target: str,
    observed_column: str,
    location_column: str,
    date_column: str,
    date: str,
    main_branch: str = "main",
) -> tuple[pd.DataFrame, bool]:
    """Fetch configured ground truth from the repository state at ``date``."""
    date_obj = datetime.strptime(date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    repo = pygit2.Repository(hub_path)

    commit = repo[repo.head.target]
    closest_commit = None
    while commit:
        if commit.commit_time <= date_obj.timestamp():
            closest_commit = commit
            break
        if not commit.parents:
            break
        commit = commit.parents[0]

    if closest_commit is None:
        raise ValueError(f"No commit found for date {date} in repo {hub_path} history")

    repo.checkout_tree(closest_commit.tree, strategy=pygit2.GIT_CHECKOUT_FORCE)
    repo.set_head(closest_commit.id)
    logger.info(
        "Checked out commit on %s (SHA: %s, %s) for repo %s",
        date,
        closest_commit.id,
        closest_commit.commit_time,
        hub_path,
    )

    try:
        gt = _read_ground_truth_file(hub_path, gt_file)
        _validate_columns(gt, [date_column, location_column, observed_column])
        gt, target_column_found = _filter_target_if_present(gt, target)
        gt = _resolve_duplicates(gt, vintage_date=date, gt_file=gt_file)

        return (
            _keep_output_columns(gt, date_column, location_column, observed_column, target),
            target_column_found,
        )
    finally:
        repo.checkout(f"refs/heads/{main_branch}", strategy=pygit2.GIT_CHECKOUT_FORCE)


def _asof_gt_fetch(
    hub_path: Path,
    gt_file: str,
    target: str,
    observed_column: str,
    location_column: str,
    date_column: str,
    date_s: list[str] | str,
) -> tuple[pd.DataFrame, str, bool]:
    """Fetch configured ground truth and select the newest as-of revision per key."""
    cutoff_date = max(date_s) if isinstance(date_s, list) else date_s
    gt = _read_ground_truth_file(hub_path, gt_file)
    _validate_columns(gt, [date_column, location_column, observed_column])
    gt, target_column_found = _filter_target_if_present(gt, target)
    gt = _resolve_duplicates(gt, vintage_date=cutoff_date, gt_file=gt_file)
    gt = _filter_to_cutoff_target_end_date(gt, cutoff_date, date_column)

    if gt.empty:
        raise ValueError(
            f"Ground truth data does not contain target {target!r} through {cutoff_date}."
        )

    return (
        _keep_output_columns(gt, date_column, location_column, observed_column, target),
        cutoff_date,
        target_column_found,
    )


def gt_from_hub(
    hub_path: Path,
    target: str,
    reference_dates: list[str],
    gt_file: str,
    observed_column: str,
    location_column: str,
    date_column: str,
    data_cutoff_dates: list[str],
    vintaging: bool,
    vintaging_method: str | None,
) -> dict[str, pd.DataFrame]:
    """Fetch configured ground truth with the requested vintaging strategy."""
    if len(reference_dates) != len(data_cutoff_dates):
        raise ValueError("`reference_dates` and `data_cutoff_dates` must have the same length.")

    gt_dict = {}
    target_column_presence = []
    if vintaging:
        for reference_date, cutoff_date in zip(reference_dates, data_cutoff_dates):
            if vintaging_method == "checkout":
                gt, target_column_found = _checkout_gt_fetch(
                    hub_path=hub_path,
                    gt_file=gt_file,
                    target=target,
                    observed_column=observed_column,
                    location_column=location_column,
                    date_column=date_column,
                    date=cutoff_date,
                )
                gt_dict[str(reference_date)] = _filter_to_reference_season(gt, reference_date)
            elif vintaging_method == "as_of":
                gt, _, target_column_found = _asof_gt_fetch(
                    hub_path=hub_path,
                    gt_file=gt_file,
                    target=target,
                    observed_column=observed_column,
                    location_column=location_column,
                    date_column=date_column,
                    date_s=cutoff_date,
                )
                gt_dict[str(reference_date)] = _filter_to_reference_season(gt, reference_date)
            else:
                raise ValueError(f"Unsupported `vintaging_method`: {vintaging_method!r}.")
            target_column_presence.append(target_column_found)
    else:
        gt, _, target_column_found = _asof_gt_fetch(
            hub_path=hub_path,
            gt_file=gt_file,
            target=target,
            observed_column=observed_column,
            location_column=location_column,
            date_column=date_column,
            date_s=data_cutoff_dates,
        )
        gt_dict[str(reference_dates[-1])] = _filter_to_reference_season(
            gt, reference_dates[-1]
        )
        target_column_presence.append(target_column_found)

    if len(set(target_column_presence)) > 1:
        raise ValueError(
            "Configured ground truth files inconsistently contain a `target` column across "
            "the requested vintages. Ground truth file must have consistent columns across all dates."
        )
    if target_column_presence and not target_column_presence[0]:
        logger.warning(
            "Unable to verify configured target %r because the ground truth data file does not "
            "contain a `target` column.",
            target,
        )

    logger.info("Success ✅")
    return gt_dict
