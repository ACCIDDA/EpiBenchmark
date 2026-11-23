"""Retrieve and standardize ground truth for the ``epibench create`` pipeline."""

import importlib
import io
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import polars as pl
import pygit2
from dateutil.parser import parse as parse_datetime

from .dataframes import date_value, normalize_dates, read_csv, to_polars

logger = logging.getLogger(__name__)
hub_target_data_schema_module = importlib.import_module(
    "hubdata.create_target_data_schema"
)

AS_OF_COLUMN = "as_of"


@dataclass
class CoverageExpectations:
    """Date/location grid from the source before cutoff and revision selection."""

    dates: list[str]
    locations: list[object]


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


def _read_ground_truth_file(
    hub_path: Path,
    gt_file: str,
    location_column: str | list[str] | None = None,
    contents: bytes | None = None,
) -> pl.DataFrame:
    """Read the configured file, optionally from a historical Git blob."""
    ground_truth_path = _ground_truth_path(hub_path, gt_file)
    if contents is None and not ground_truth_path.is_file():
        raise FileNotFoundError(
            f"Could not find configured ground truth file {gt_file!r} in hub repository {hub_path}."
        )

    if ground_truth_path.suffix.lower() == ".parquet":
        source = ground_truth_path if contents is None else io.BytesIO(contents)
        return to_polars(pl.read_parquet(source))
    if ground_truth_path.suffix.lower() == ".csv":
        source = ground_truth_path if contents is None else contents
        names = (
            location_column if isinstance(location_column, list) else [location_column]
        )
        frame = read_csv(
            source, string_columns=tuple(name for name in names if name is not None)
        )
        location_names = [
            name for name in dict.fromkeys(names) if name in frame.columns
        ]
        if location_names:
            # The shared reader treats tokens such as "NA" as missing. In a
            # location column requested for exact matching, they are literal codes.
            literal_locations = pl.read_csv(
                source,
                columns=location_names,
                schema_overrides={name: pl.String for name in location_names},
                missing_utf8_is_empty_string=True,
            )
            frame = frame.with_columns(literal_locations.get_columns())
        return frame

    raise ValueError("`ground_truth_file` must point to a .csv or .parquet file.")


def _resolve_columns(
    df: pl.DataFrame,
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


def _filter_target_if_present(
    df: pl.DataFrame, target: str
) -> tuple[pl.DataFrame, bool]:
    """Filter the requested target when the source data supplies a target column."""
    if "target" not in df.columns:
        return df, False

    if df.schema["target"] not in (pl.String, pl.Categorical, pl.Enum):
        raise ValueError(f"Could not find target {target!r} in ground truth data.")
    filtered_df = df.filter(pl.col("target") == target)
    if filtered_df.is_empty():
        raise ValueError(f"Could not find target {target!r} in ground truth data.")
    return filtered_df, True


def _filter_locations(
    df: pl.DataFrame, location_column: str, locations: list[str] | None
) -> pl.DataFrame:
    """Select exact location values, rejecting requests absent from the source."""
    if locations is None:
        return df
    available = set(df[location_column].unique().to_list())
    missing = [
        location for location in dict.fromkeys(locations) if location not in available
    ]
    if missing:
        raise ValueError(
            f"Could not find requested `locations` {missing!r} in ground truth "
            f"column {location_column!r} for the selected target. "
            "Location values must match exactly."
        )
    return df.filter(pl.col(location_column).is_in(locations))


def _coverage_expectations(
    df: pl.DataFrame,
    date_column: str,
    location_column: str,
    locations: list[str] | None,
) -> CoverageExpectations:
    """Retain the source's date/location grid before selection and vintaging."""
    return CoverageExpectations(
        dates=df[date_column]
        .drop_nulls()
        .unique()
        .sort()
        .dt.to_string("%Y-%m-%d")
        .to_list(),
        locations=(
            list(dict.fromkeys(locations))
            if locations is not None
            else df[location_column].drop_nulls().unique(maintain_order=True).to_list()
        ),
    )


def _as_of_timestamps(values: pl.Series) -> pl.Series:
    """Convert mixed revision timestamps to UTC while retaining ISO nanoseconds."""
    dtype = pl.Datetime("ns", time_zone="UTC")
    if values.dtype.is_numeric():
        return values.cast(pl.Int64, strict=False).cast(dtype)
    if values.dtype == pl.Date or isinstance(values.dtype, pl.Datetime):
        return values.cast(dtype)

    text = values.cast(pl.String).str.strip_chars()
    column = pl.col(values.name)
    timestamps = (
        text.to_frame()
        .select(
            pl.coalesce(
                column.str.to_datetime(
                    format=fmt, time_unit="ns", time_zone="UTC", strict=False
                )
                for fmt in (
                    "%+",
                    "%Y-%m-%d",
                    "%Y-%m-%dT%H:%M:%S%.f",
                    "%Y-%m-%d %H:%M:%S%.f",
                )
            ).alias(values.name)
        )
        .to_series()
    )
    if timestamps.is_null().any():
        fallback = {}
        for value in text.filter(text.is_not_null() & timestamps.is_null()).unique():
            try:
                parsed = parse_datetime(value, default=datetime(1, 1, 1))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                fallback[value] = parsed.astimezone(timezone.utc)
            except (OverflowError, ValueError):
                fallback[value] = None
        if fallback:
            parsed = text.replace_strict(
                fallback, default=None, return_dtype=pl.Datetime("us", time_zone="UTC")
            )
            timestamps = timestamps.fill_null(parsed.cast(dtype))
    return timestamps


def _resolve_duplicates(
    df: pl.DataFrame,
    vintage_date: str,
    gt_file: str,
    *,
    date_column: str,
    location_column: str,
    observed_column: str,
) -> pl.DataFrame:
    """Keep one observation per date/location/target, resolving eligible revisions.

    Values and source metadata are not observation identifiers. Identical values
    may collapse; conflicting values need an unambiguous latest ``as_of``.
    """
    key_columns = [date_column, location_column]
    if "target" in df.columns and "target" not in key_columns:
        key_columns.append("target")

    available_df = df
    has_as_of = AS_OF_COLUMN in df.columns
    if has_as_of:
        as_of_values = _as_of_timestamps(df[AS_OF_COLUMN])
        if as_of_values.is_null().any():
            raise ValueError(
                "Ground truth data contains missing or invalid `as_of` values."
            )

        # Cutoff dates include the whole calendar day, including timestamped revisions.
        cutoff_exclusive = datetime.fromisoformat(vintage_date).replace(
            tzinfo=timezone.utc
        ) + timedelta(days=1)
        sort_column = "_as_of_sort_value"
        while sort_column in df.columns:
            sort_column += "_"
        timestamp = pl.col(sort_column)
        available_df = df.with_columns(as_of_values.alias(sort_column)).filter(
            timestamp < cutoff_exclusive
        )
        if available_df.is_empty():
            raise ValueError(
                f"Ground truth data does not contain an `as_of` vintage on or before {vintage_date}."
            )

        available_df = available_df.filter(
            timestamp == timestamp.max().over(key_columns)
        ).drop(sort_column)

    conflicts = (
        available_df.filter(pl.col(observed_column).n_unique().over(key_columns) > 1)
        .select(key_columns)
        .unique(maintain_order=True)
        .head(5)
    )
    if not conflicts.is_empty():
        reason = (
            "the latest eligible `as_of` timestamp has conflicting observed values"
            if has_as_of
            else "no `as_of` column is present to resolve conflicting observed values"
        )
        raise ValueError(
            f"Ambiguous ground truth in {gt_file!r} for vintage {vintage_date}: "
            f"{reason}. Conflicting {key_columns} keys "
            f"(up to 5 shown): {conflicts.rows()!r}."
        )

    return available_df.unique(subset=key_columns, keep="last", maintain_order=True)


def _filter_to_cutoff_target_end_date(
    df: pl.DataFrame, cutoff_date: str, date_column: str
) -> pl.DataFrame:
    """Keep observations whose target end date is no later than the requested cutoff."""
    return df.filter(pl.col(date_column) <= date_value(cutoff_date))


def _keep_output_columns(
    df: pl.DataFrame,
    date_column: str,
    location_column: str,
    observed_column: str,
    target: str,
) -> pl.DataFrame:
    """Return standardized create-pipeline columns, including ``target`` and ``observed``."""
    return df.select(
        pl.col(date_column).alias("target_end_date"),
        pl.col(location_column).alias("location"),
        pl.col("target") if "target" in df.columns else pl.lit(target).alias("target"),
        pl.col(observed_column).alias("observed"),
    )


def _prepare_ground_truth(
    gt: pl.DataFrame,
    *,
    gt_file: str,
    target: str,
    observed_column: str | list[str],
    location_column: str | list[str],
    date_column: str | list[str],
    cutoff_date: str,
    locations: list[str] | None,
) -> tuple[pl.DataFrame, bool, CoverageExpectations]:
    date_column, location_column, observed_column = _resolve_columns(
        gt, date_column, location_column, observed_column
    )
    gt, target_column_found = _filter_target_if_present(gt, target)
    gt = normalize_dates(gt, [date_column], strict=False)
    coverage = _coverage_expectations(gt, date_column, location_column, locations)
    gt = _filter_locations(gt, location_column, locations)
    gt = _filter_to_cutoff_target_end_date(gt, cutoff_date, date_column)
    gt = _resolve_duplicates(
        gt,
        vintage_date=cutoff_date,
        gt_file=gt_file,
        date_column=date_column,
        location_column=location_column,
        observed_column=observed_column,
    )
    return (
        _keep_output_columns(gt, date_column, location_column, observed_column, target),
        target_column_found,
        coverage,
    )


def _checkout_gt_fetch(
    hub_path: Path,
    gt_file: str,
    target: str,
    observed_column: str | list[str],
    location_column: str | list[str],
    date_column: str | list[str],
    date: str,
    locations: list[str] | None = None,
) -> tuple[pl.DataFrame, bool, CoverageExpectations]:
    """Read historical ground truth at ``date`` without changing the hub checkout."""
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

    # Validate the configured relative path, then read its historical blob.
    _ground_truth_path(hub_path, gt_file)
    try:
        contents = repo[closest_commit.tree[gt_file].id].data
    except KeyError as error:
        raise FileNotFoundError(
            f"Could not find configured ground truth file {gt_file!r} at commit {closest_commit.id}."
        ) from error
    logger.info(
        "Reading snapshot on %s (SHA: %s, %s) for repo %s",
        date,
        closest_commit.id,
        closest_commit.commit_time,
        hub_path,
    )

    gt = _read_ground_truth_file(
        hub_path,
        gt_file,
        location_column if locations is not None else None,
        contents=contents,
    )
    return _prepare_ground_truth(
        gt,
        gt_file=gt_file,
        target=target,
        observed_column=observed_column,
        location_column=location_column,
        date_column=date_column,
        cutoff_date=date,
        locations=locations,
    )


def _asof_gt_fetch(
    hub_path: Path,
    gt_file: str,
    target: str,
    observed_column: str | list[str],
    location_column: str | list[str],
    date_column: str | list[str],
    date_s: list[str] | str,
    locations: list[str] | None = None,
    source_data: pl.DataFrame | None = None,
) -> tuple[pl.DataFrame, bool, CoverageExpectations]:
    """Fetch configured ground truth and select the newest as-of revision per key."""
    cutoff_date = max(date_s) if isinstance(date_s, list) else date_s
    gt = source_data
    if gt is None:
        gt = _read_ground_truth_file(
            hub_path, gt_file, location_column if locations is not None else None
        )
    gt, target_column_found, coverage = _prepare_ground_truth(
        gt,
        gt_file=gt_file,
        target=target,
        observed_column=observed_column,
        location_column=location_column,
        date_column=date_column,
        cutoff_date=cutoff_date,
        locations=locations,
    )

    if gt.is_empty():
        raise ValueError(
            f"Ground truth data does not contain target {target!r} through {cutoff_date}."
        )

    return gt, target_column_found, coverage


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
    *,
    coverage_by_date: dict[str, CoverageExpectations] | None = None,
) -> dict[str, pl.DataFrame]:
    """Fetch all available history through each cutoff, with eligible revisions only.

    Reference-date seasons restrict forecast tasks, never the observation history.
    If supplied, ``coverage_by_date`` receives the source grid for each result.
    """
    if len(reference_dates) != len(data_cutoff_dates):
        raise ValueError(
            "`reference_dates` and `data_cutoff_dates` must have the same length."
        )

    gt_dict = {}
    coverage_results = {}
    target_column_presence = []
    if vintaging:
        # Each as-of vintage uses the same source snapshot.
        asof_source = (
            _read_ground_truth_file(
                hub_path, gt_file, location_column if locations is not None else None
            )
            if vintaging_method == "as_of" and reference_dates
            else None
        )
        for reference_date, cutoff_date in zip(reference_dates, data_cutoff_dates):
            if vintaging_method == "checkout":
                gt, target_column_found, coverage = _checkout_gt_fetch(
                    hub_path=hub_path,
                    gt_file=gt_file,
                    target=target,
                    observed_column=observed_column,
                    location_column=location_column,
                    date_column=date_column,
                    date=cutoff_date,
                    locations=locations,
                )
            elif vintaging_method == "as_of":
                gt, target_column_found, coverage = _asof_gt_fetch(
                    hub_path=hub_path,
                    gt_file=gt_file,
                    target=target,
                    observed_column=observed_column,
                    location_column=location_column,
                    date_column=date_column,
                    date_s=cutoff_date,
                    locations=locations,
                    source_data=asof_source,
                )
            else:
                raise ValueError(
                    f"Unsupported `vintaging_method`: {vintaging_method!r}."
                )
            gt_dict[str(reference_date)] = gt
            coverage_results[str(reference_date)] = coverage
            target_column_presence.append(target_column_found)
    else:
        gt, target_column_found, coverage = _asof_gt_fetch(
            hub_path=hub_path,
            gt_file=gt_file,
            target=target,
            observed_column=observed_column,
            location_column=location_column,
            date_column=date_column,
            date_s=data_cutoff_dates,
            locations=locations,
        )
        gt_dict[str(reference_dates[-1])] = gt
        coverage_results[str(reference_dates[-1])] = coverage
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

    if coverage_by_date is not None:
        coverage_by_date.update(coverage_results)
    logger.info("Success ✅")
    return gt_dict