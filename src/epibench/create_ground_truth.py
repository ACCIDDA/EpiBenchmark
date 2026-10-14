"""Retrieve and standardize ground truth for the ``epibench create`` pipeline."""

import importlib
import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import polars as pl

from .dataframes import to_polars, normalize_dates, date_value, read_csv
import pygit2

from .hub_date_utils import create_season_start


logger = logging.getLogger(__name__)
hub_target_data_schema_module = importlib.import_module(
    "hubdata.create_target_data_schema"
)

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
        raise ValueError(
            "`ground_truth_file` must be a path relative to the hub repository root."
        )

    resolved_hub_path = hub_path.resolve()
    resolved_gt_path = (resolved_hub_path / relative_path).resolve()
    try:
        resolved_gt_path.relative_to(resolved_hub_path)
    except ValueError as error:
        raise ValueError(
            "`ground_truth_file` must not resolve outside the hub repository."
        ) from error

    return resolved_gt_path


def _read_ground_truth_file(hub_path: Path, gt_file: str) -> pl.DataFrame:
    """Read the configured CSV or Parquet ground truth file from a hub checkout."""
    ground_truth_path = _ground_truth_path(hub_path, gt_file)
    if not ground_truth_path.is_file():
        raise FileNotFoundError(
            f"Could not find configured ground truth file {gt_file!r} in hub repository {hub_path}."
        )

    if ground_truth_path.suffix.lower() == ".parquet":
        return pl.read_parquet(ground_truth_path)
    if ground_truth_path.suffix.lower() == ".csv":
        return read_csv(ground_truth_path)

    raise ValueError("`ground_truth_file` must point to a .csv or .parquet file.")


def _validate_columns(df: pl.DataFrame, required_columns: list[str]) -> None:
    """Require all columns needed to construct the create-pipeline output."""
    missing_columns = set(required_columns).difference(df.columns)
    if missing_columns:
        raise ValueError(
            "Ground truth data is missing required column(s): "
            f"{', '.join(sorted(missing_columns))}."
        )


def _filter_target_if_present(
    df: pl.DataFrame, target: str
) -> tuple[pl.DataFrame, bool]:
    """Filter the requested target when the source data supplies a target column."""
    if "target" not in df.columns:
        return df, False

    filtered_df = df.filter(pl.col("target") == target)
    if filtered_df.is_empty():
        raise ValueError(f"Could not find target {target!r} in ground truth data.")
    return filtered_df, True


def _resolve_duplicates(
    df: pl.DataFrame, vintage_date: str, gt_file: str
) -> pl.DataFrame:
    """Resolve duplicates across the complete schema using the newest vintage."""
    df = to_polars(df)
    if AS_OF_COLUMN not in df.columns:
        duplicate_rows = df.filter(df.is_duplicated())
        if duplicate_rows.is_empty():
            return df
        raise ValueError(
            f"DUPLICATES DETECTED: {duplicate_rows.to_dicts()}\n"
            "COULD NOT RESOLVE DUPLICATES BECAUSE NO `as_of` column is present in "
            f"{gt_file}."
        )
    as_of_values = normalize_dates(
        df.select(AS_OF_COLUMN), [AS_OF_COLUMN], strict=False
    )[AS_OF_COLUMN]
    if as_of_values.is_null().any():
        raise ValueError(
            "Ground truth data contains missing or invalid `as_of` values."
        )
    available = df.with_columns(as_of_values.alias("_as_of_sort_value")).filter(
        pl.col("_as_of_sort_value") <= date_value(vintage_date)
    )
    if available.is_empty():
        raise ValueError(
            f"Ground truth data does not contain an `as_of` vintage on or before {vintage_date}."
        )
    return (
        available.sort("_as_of_sort_value", maintain_order=True)
        .unique(
            subset=[c for c in df.columns if c != AS_OF_COLUMN],
            keep="last",
            maintain_order=True,
        )
        .drop("_as_of_sort_value")
    )


def _filter_to_cutoff_target_end_date(
    df: pl.DataFrame, cutoff_date: str, date_column: str
) -> pl.DataFrame:
    dates = normalize_dates(df.select(date_column), [date_column], strict=False)[
        date_column
    ]
    return df.filter(dates <= date_value(cutoff_date))


def _keep_output_columns(
    df: pl.DataFrame,
    date_column: str,
    location_column: str,
    observed_column: str,
    target: str,
) -> pl.DataFrame:
    """Return the existing standardized create-pipeline schema."""
    return df.select(
        pl.col(date_column).alias("target_end_date"),
        pl.col(location_column).alias("location"),
        pl.col("target") if "target" in df.columns else pl.lit(target).alias("target"),
        pl.col(observed_column).alias("observed"),
    )


def _filter_to_reference_season(df: pl.DataFrame, reference_date: str) -> pl.DataFrame:
    """Keep observations from July 1 through the task reference date."""
    reference_day = date_value(reference_date).date()
    dates = normalize_dates(
        df.select("target_end_date"), ["target_end_date"], strict=False
    )["target_end_date"].dt.date()
    return df.filter(
        dates.is_between(create_season_start(reference_day), reference_day)
    )


def _checkout_gt_fetch(
    hub_path: Path,
    gt_file: str,
    target: str,
    observed_column: str,
    location_column: str,
    date_column: str,
    date: str,
    main_branch: str = "main",
) -> tuple[pl.DataFrame, bool]:
    """Fetch configured ground truth from the repository state at ``date``."""
    date_obj = datetime.strptime(date, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59
    )
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
            _keep_output_columns(
                gt, date_column, location_column, observed_column, target
            ),
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
    source_data: pl.DataFrame | None = None,
) -> tuple[pl.DataFrame, str, bool]:
    """Fetch configured ground truth and select the newest as-of revision per key."""
    cutoff_date = max(date_s) if isinstance(date_s, list) else date_s
    gt = (
        source_data
        if source_data is not None
        else _read_ground_truth_file(hub_path, gt_file)
    )
    _validate_columns(gt, [date_column, location_column, observed_column])
    gt, target_column_found = _filter_target_if_present(gt, target)
    gt = _resolve_duplicates(gt, vintage_date=cutoff_date, gt_file=gt_file)
    gt = _filter_to_cutoff_target_end_date(gt, cutoff_date, date_column)

    if gt.is_empty():
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
) -> dict[str, pl.DataFrame]:
    """Fetch configured ground truth with the requested vintaging strategy."""
    if len(reference_dates) != len(data_cutoff_dates):
        raise ValueError(
            "`reference_dates` and `data_cutoff_dates` must have the same length."
        )

    gt_dict = {}
    target_column_presence = []
    if vintaging:
        # As-of vintages share one immutable source snapshot; checkout vintages
        # must still read each historical repository state independently.
        asof_source = (
            _read_ground_truth_file(hub_path, gt_file)
            if vintaging_method == "as_of"
            else None
        )
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
                gt_dict[str(reference_date)] = _filter_to_reference_season(
                    gt, reference_date
                )
            elif vintaging_method == "as_of":
                gt, _, target_column_found = _asof_gt_fetch(
                    hub_path=hub_path,
                    gt_file=gt_file,
                    target=target,
                    observed_column=observed_column,
                    location_column=location_column,
                    date_column=date_column,
                    date_s=cutoff_date,
                    source_data=asof_source,
                )
                gt_dict[str(reference_date)] = _filter_to_reference_season(
                    gt, reference_date
                )
            else:
                raise ValueError(
                    f"Unsupported `vintaging_method`: {vintaging_method!r}."
                )
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
