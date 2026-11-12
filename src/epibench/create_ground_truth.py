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


def _read_ground_truth_file(
    hub_path: Path,
    gt_file: str,
    location_column: str | list[str] | None = None,
) -> pd.DataFrame:
    """Read the configured CSV or Parquet ground truth file from a hub checkout."""
    ground_truth_path = _ground_truth_path(hub_path, gt_file)
    if not ground_truth_path.is_file():
        raise FileNotFoundError(
            f"Could not find configured ground truth file {gt_file!r} in hub repository {hub_path}."
        )

    if ground_truth_path.suffix.lower() == ".parquet":
        return pd.read_parquet(ground_truth_path)
    if ground_truth_path.suffix.lower() == ".csv":
        # Preserve literal CSV location codes (including leading zeros) when
        # exact string selection is requested. Missing fallback names are ignored.
        names = location_column if isinstance(location_column, list) else [location_column]
        converters = {name: str for name in names if name is not None}
        return pd.read_csv(ground_truth_path, low_memory=False, converters=converters)

    raise ValueError("`ground_truth_file` must point to a .csv or .parquet file.")


def _resolve_columns(
    df: pd.DataFrame,
    date_column: str | list[str],
    location_column: str | list[str],
    observed_column: str | list[str],
) -> tuple[str, str, str]:
    """Choose the first available name for each role in this source file."""
    resolved = []
    for parameter, names in (
        ("date_column_name", date_column),
        ("location_column_name", location_column),
        ("observed_column_name", observed_column),
    ):
        candidates = names if isinstance(names, list) else [names]
        column = next((name for name in candidates if name in df.columns), None)
        if column is None:
            raise ValueError(
                f"Ground truth data is missing a required column for `{parameter}`. "
                f"Tried: {candidates!r}. Available columns: {list(df.columns)!r}."
            )
        resolved.append(column)

    if len(set(resolved)) != len(resolved):
        raise ValueError(
            "`date_column_name`, `location_column_name`, and `observed_column_name` "
            f"must resolve to distinct columns. Resolved columns: {resolved!r}."
        )
    return resolved[0], resolved[1], resolved[2]


def _filter_target_if_present(df: pd.DataFrame, target: str) -> tuple[pd.DataFrame, bool]:
    """Filter the requested target when the source data supplies a target column."""
    if "target" not in df.columns:
        return df, False

    filtered_df = df[df["target"] == target].copy()
    if filtered_df.empty:
        raise ValueError(f"Could not find target {target!r} in ground truth data.")
    return filtered_df, True


def _filter_locations(
    df: pd.DataFrame, location_column: str, locations: list[str] | None
) -> pd.DataFrame:
    """Select exact location values, rejecting requests absent from the source."""
    if locations is None:
        return df
    available = df[location_column]
    requested = pd.Series(list(dict.fromkeys(locations)))
    missing = requested.loc[~requested.isin(available)].tolist()
    if missing:
        raise ValueError(
            f"Could not find requested `locations` {missing!r} in ground truth "
            f"column {location_column!r} for the selected target. "
            "Location values must match exactly."
        )
    return df.loc[available.isin(locations)].copy()


def _record_coverage_expectations(
    df: pd.DataFrame,
    date_column: str,
    location_column: str,
    locations: list[str] | None,
) -> None:
    """Retain the source's date/location grid before selection and vintaging."""
    df.attrs["create_coverage"] = {
        "dates": sorted(
            pd.to_datetime(df[date_column], errors="coerce")
            .dropna().dt.strftime("%Y-%m-%d").unique()
        ),
        "locations": (
            list(dict.fromkeys(locations)) if locations is not None
            else df[location_column].dropna().unique().tolist()
        ),
    }


def _resolve_duplicates(
    df: pd.DataFrame,
    vintage_date: str,
    gt_file: str,
    *,
    date_column: str,
    location_column: str,
    observed_column: str,
) -> pd.DataFrame:
    """Keep one observation per date/location/target, resolving eligible revisions.

    Values and source metadata are not observation identifiers. Identical values
    may collapse; conflicting values need an unambiguous latest ``as_of``.
    """
    key_columns = [date_column, location_column]
    if "target" in df.columns:
        key_columns.append("target")

    available_df = df.copy()
    has_as_of = AS_OF_COLUMN in available_df.columns
    if has_as_of:
        as_of_values = pd.to_datetime(
            available_df[AS_OF_COLUMN], errors="coerce", utc=True, format="mixed"
        )
        if as_of_values.isna().any():
            raise ValueError("Ground truth data contains missing or invalid `as_of` values.")

        # Cutoff dates include the whole calendar day, including timestamped revisions.
        cutoff_exclusive = pd.Timestamp(vintage_date, tz="UTC") + pd.Timedelta(days=1)
        available_df = available_df.assign(_as_of_sort_value=as_of_values)
        available_df = available_df[available_df["_as_of_sort_value"] < cutoff_exclusive]
        if available_df.empty:
            raise ValueError(
                f"Ground truth data does not contain an `as_of` vintage on or before {vintage_date}."
            )

        latest_as_of = available_df.groupby(key_columns, dropna=False)[
            "_as_of_sort_value"
        ].transform("max")
        available_df = available_df[
            available_df["_as_of_sort_value"].eq(latest_as_of)
        ]

    value_counts = available_df.groupby(key_columns, dropna=False)[
        observed_column
    ].nunique(dropna=False)
    conflicts = value_counts[value_counts > 1]
    if not conflicts.empty:
        reason = (
            "the latest eligible `as_of` timestamp has conflicting observed values"
            if has_as_of
            else "no `as_of` column is present to resolve conflicting observed values"
        )
        raise ValueError(
            f"Ambiguous ground truth in {gt_file!r} for vintage {vintage_date}: "
            f"{reason}. Conflicting {key_columns} keys "
            f"(up to 5 shown): {conflicts.index.tolist()[:5]!r}."
        )

    return available_df.drop_duplicates(subset=key_columns, keep="last").drop(
        columns="_as_of_sort_value", errors="ignore"
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
    observed_column: str | list[str],
    location_column: str | list[str],
    date_column: str | list[str],
    date: str,
    main_branch: str = "main",
    locations: list[str] | None = None,
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
        gt = _read_ground_truth_file(
            hub_path, gt_file, location_column if locations is not None else None
        )
        date_column, location_column, observed_column = _resolve_columns(
            gt, date_column, location_column, observed_column
        )
        gt, target_column_found = _filter_target_if_present(gt, target)
        _record_coverage_expectations(gt, date_column, location_column, locations)
        gt = _filter_locations(gt, location_column, locations)
        gt = _resolve_duplicates(
            gt, vintage_date=date, gt_file=gt_file,
            date_column=date_column, location_column=location_column,
            observed_column=observed_column,
        )

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
    observed_column: str | list[str],
    location_column: str | list[str],
    date_column: str | list[str],
    date_s: list[str] | str,
    locations: list[str] | None = None,
) -> tuple[pd.DataFrame, str, bool]:
    """Fetch configured ground truth and select the newest as-of revision per key."""
    cutoff_date = max(date_s) if isinstance(date_s, list) else date_s
    gt = _read_ground_truth_file(
        hub_path, gt_file, location_column if locations is not None else None
    )
    date_column, location_column, observed_column = _resolve_columns(
        gt, date_column, location_column, observed_column
    )
    gt, target_column_found = _filter_target_if_present(gt, target)
    _record_coverage_expectations(gt, date_column, location_column, locations)
    gt = _filter_locations(gt, location_column, locations)
    gt = _resolve_duplicates(
        gt, vintage_date=cutoff_date, gt_file=gt_file,
        date_column=date_column, location_column=location_column,
        observed_column=observed_column,
    )
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
    observed_column: str | list[str],
    location_column: str | list[str],
    date_column: str | list[str],
    data_cutoff_dates: list[str],
    vintaging: bool,
    vintaging_method: str | None,
    locations: list[str] | None = None,
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
                    locations=locations,
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
                    locations=locations,
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
            locations=locations,
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
