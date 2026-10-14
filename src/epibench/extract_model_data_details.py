"""Function to gather information about the model data to be scored."""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

import polars as pl

from .dataframes import to_polars, is_dataframe, normalize_dates, date_value
from hubdata import connect_hub

from .horizon_utils import (
    normalize_horizon_strings,
    normalize_horizon_column,
    sort_horizon_strings,
)
from .scoring_summary import record_filtered_facets
from .table_files import read_forecasts

REQUIRED_MODEL_DATA_COLUMNS = [
    "reference_date",
    "target",
    "horizon",
    "target_end_date",
    "location",
    "output_type",
    "output_type_id",
    "value",
]
MODEL_DATA_STRING_COLUMNS = {
    "reference_date": str,
    "target": str,
    "horizon": str,
    "target_end_date": str,
    "location": str,
    "output_type": str,
    "output_type_id": str,
}
logger = logging.getLogger(__name__)


def _stringify_challenge_facets(
    required_reference_dates: List[str],
    required_locations: List[str],
    required_horizons: List[str],
) -> Tuple[Set[str], Set[str], Set[str]]:
    """Normalize library challenge facets into comparable string sets."""
    normalized_required_reference_dates = {
        date_value(reference_date).strftime("%Y-%m-%d")
        for reference_date in required_reference_dates
    }
    normalized_required_locations = {str(location) for location in required_locations}
    normalized_required_horizons = set(normalize_horizon_strings(required_horizons))
    return (
        normalized_required_reference_dates,
        normalized_required_locations,
        normalized_required_horizons,
    )


def _filter_to_required_challenge_facets(
    df: pl.DataFrame,
    model_name: str,
    csv_name: str,
    normalized_required_reference_dates: Set[str],
    normalized_required_locations: Set[str],
    normalized_required_horizons: Set[str],
    filtered_facets_by_file: Optional[Dict[str, Set[str]]] = None,
) -> pl.DataFrame:
    """
    Given reference_dates, locations, and horizons lists specified in the library challenge,
    filter out any excess values found and record them for summary output.
    """

    df = normalize_dates(to_polars(df), ["reference_date"], strings=True)
    masks = {
        "reference_date": pl.col("reference_date").is_in(
            sorted(normalized_required_reference_dates)
        ),
        "location": pl.col("location").is_in(sorted(normalized_required_locations)),
        "horizon": pl.col("horizon").is_in(sorted(normalized_required_horizons)),
    }
    filtered_facet_names = [
        name for name, mask in masks.items() if df.select((~mask).any()).item()
    ]
    record_filtered_facets(
        filtered_facets_by_file=filtered_facets_by_file,
        input_file=csv_name,
        facets=filtered_facet_names,
    )
    return df.filter(pl.all_horizontal(*masks.values()))


def _validate_required_challenge_grid(
    df: pl.DataFrame,
    model_name: str,
    normalized_required_reference_dates: Set[str],
    normalized_required_locations: Set[str],
    normalized_required_horizons: Set[str],
) -> None:
    """
    Ensure all required challenge forecast units exist.

    For library challenges, a required forecast unit is the required
    combination of reference_date, location, and horizon.
    """
    sorted_required_horizons = sort_horizon_strings(normalized_required_horizons)
    expected_rows = []
    for reference_date in sorted(normalized_required_reference_dates):
        for location in sorted(normalized_required_locations):
            for horizon in sorted_required_horizons:
                expected_rows.append(
                    {
                        "reference_date": reference_date,
                        "location": location,
                        "horizon": horizon,
                    }
                )
    columns = ["reference_date", "location", "horizon"]
    expected = pl.DataFrame(expected_rows, schema={c: pl.String for c in columns})
    observed = (
        normalize_dates(to_polars(df), ["reference_date"], strings=True)
        .select(columns)
        .unique(maintain_order=True)
    )
    missing_df = expected.join(
        observed, on=columns, how="anti", maintain_order="left", nulls_equal=True
    )
    if not missing_df.is_empty():
        grouped = missing_df.group_by(
            ["reference_date", "location"], maintain_order=True
        ).agg(pl.col("horizon"))
        details = [
            f"{row['reference_date']}, location {row['location']}: missing horizons {', '.join(sort_horizon_strings(row['horizon']))}"
            for row in grouped.iter_rows(named=True)
        ]
        details_text = "\n".join(details)
        raise ValueError(
            f"Model '{model_name}' is missing {len(missing_df)} required "
            "forecast unit combination(s) for this library challenge.\n"
            "Every required reference_date/location/horizon forecast unit "
            "must be present in the input model data before a scorecard can be generated.\n"
            f"{details_text}"
        )


def _extra_models(
    hub_path: Path,
    model_name: str,
    eval_start_date: str,
    eval_end_date: str,
    target: str,
    locations: List[str],
    allowed_forecast_units: Optional[pl.DataFrame] = None,
    required_reference_dates: Optional[List[str]] = None,
    required_locations: Optional[List[str]] = None,
    required_horizons: Optional[List[str]] = None,
) -> pl.DataFrame:
    """
    write
    """
    # use hubdata connect_hub() to quickly pull extra model data
    try:
        hub_connection = connect_hub(hub_path=hub_path)
        data_return = pl.from_arrow(hub_connection.get_dataset().to_table())
    except Exception as e:
        raise ConnectionError(
            f"Could not establish connection to hub {hub_path} to retrieve extra "
            f"model ({model_name}) data. Error: {e}"
        )
    data_return = normalize_dates(
        to_polars(data_return), ["target_end_date", "reference_date"]
    )
    data_return = data_return.with_columns(pl.col("location").cast(pl.String))
    df = data_return.filter(
        (pl.col("model_id") == model_name)
        & pl.col("target_end_date").is_between(
            date_value(eval_start_date), date_value(eval_end_date)
        )
        & (pl.col("target") == target)
        & (pl.col("output_type") == "quantile")
        & pl.col("location").is_in(locations)
    )
    if df.is_empty():
        raise ValueError(
            f"Could not find model quantile data for model {model_name} "
            f"for target '{target}' between dates {date_value(eval_start_date).date()} and {date_value(eval_end_date).date()}. "
            f"Searched for locations found in provided model data: {locations}"
        )
    df = normalize_dates(df, ["reference_date"], strings=True).with_columns(
        pl.col("horizon", "location", "output_type_id").cast(pl.String)
    )
    df = normalize_horizon_column(df)
    if allowed_forecast_units is not None:
        allowed = normalize_dates(
            to_polars(allowed_forecast_units), ["target_end_date"]
        )
        df = df.with_columns(pl.col("target_end_date").dt.truncate("1d"))
        allowed = allowed.with_columns(pl.col("target_end_date").dt.truncate("1d"))
        df = df.join(
            allowed,
            on=["reference_date", "target_end_date", "location", "horizon"],
            how="inner",
            maintain_order="left",
            nulls_equal=True,
        )

    strict_grid_validation_enabled = all(
        value is not None
        for value in (
            required_reference_dates,
            required_locations,
            required_horizons,
        )
    )
    if strict_grid_validation_enabled:
        (
            normalized_required_reference_dates,
            normalized_required_locations,
            normalized_required_horizons,
        ) = _stringify_challenge_facets(
            required_reference_dates=required_reference_dates,
            required_locations=required_locations,
            required_horizons=required_horizons,
        )
        df = _filter_to_required_challenge_facets(
            df=df,
            model_name=model_name,
            csv_name="hub dataset",
            normalized_required_reference_dates=normalized_required_reference_dates,
            normalized_required_locations=normalized_required_locations,
            normalized_required_horizons=normalized_required_horizons,
        )
        _validate_required_challenge_grid(
            df=df,
            model_name=model_name,
            normalized_required_reference_dates=normalized_required_reference_dates,
            normalized_required_locations=normalized_required_locations,
            normalized_required_horizons=normalized_required_horizons,
        )

    # column renaming
    df = df.rename(
        {"model_id": "model", "output_type_id": "quantile_level", "value": "predicted"}
    )

    return df


def extract_model_data_details(
    hub_path: Path,
    model_info: dict[str, list[Path | pl.DataFrame]],
    include_models: list,
    eval_start_date: str,
    eval_end_date: str,
    target: str,
    required_reference_dates: Optional[List[str]] = None,
    required_locations: Optional[List[str]] = None,
    required_horizons: Optional[List[str]] = None,
    filtered_facets_by_file: Optional[Dict[str, Set[str]]] = None,
    excluded_files: Optional[Set[str]] = None,
) -> Tuple[Dict[str, pl.DataFrame], List[str]]:
    """
    Iteratively pre-process model data; run more checks

    Args:
        hub_path: A Path to the hub corresponding to model data.
        model_info: Model names mapped to lists of in-memory DataFrames or
            paths to CSV or Parquet files.
        include_models: List of model names from hub you want included
            in your scoring output.
        eval_start_date: YYYY-MM-DD date when evaluation should begin
            (inclusive).
        eval_end_date: YYYY-MM-DD date when evaluation should end
            (inclusive).
        target: Data target to be scored on. Only one target is supported per
            run.

        THESE PARAMS ARE CURRENTLY ONLY REQUIRED FOR CHALLENGE LIBRARY
        SCORECARD RUNS:
        required_reference_dates: Required reference_dates for strict
            library-challenge validation. When provided with locations and
            horizons, all combinations must appear in the user model data.
        required_locations: Required locations for strict library-challenge
            validation.
        required_horizons: Required horizons for strict library-challenge
            validation.

    Returns:
        A tuple containing:

        - A dict where keys are model names and values are pre-processed
            `polars.DataFrame` objects.
        - A deduplicated list of locations found across the processed model
            data.
    """
    # enable strict value checks if this is scorecard run
    # i.e., required values are provided as params
    strict_grid_validation_enabled = all(
        value is not None
        for value in (
            required_reference_dates,
            required_locations,
            required_horizons,
        )
    )
    normalized_required_reference_dates = set()  # type: Set[str]
    normalized_required_locations = set()  # type: Set[str]
    normalized_required_horizons = set()  # type: Set[str]
    if strict_grid_validation_enabled:
        (
            normalized_required_reference_dates,
            normalized_required_locations,
            normalized_required_horizons,
        ) = _stringify_challenge_facets(
            required_reference_dates=required_reference_dates,
            required_locations=required_locations,
            required_horizons=required_horizons,
        )

    global_locations_list = []
    model_dict = {}
    for model in model_info:

        # pathway for their specified model data
        processed_dfs = []  # keep a model-level list of all dfs
        excluded_due_to_eval_range = []
        excluded_due_to_target = []
        excluded_due_to_challenge_facets = []
        for source_number, data_source in enumerate(model_info[model], start=1):
            source_name = (
                f"{model} DataFrame {source_number}"
                if is_dataframe(data_source)
                else data_source.name
            )
            record_filtered_facets(
                filtered_facets_by_file=filtered_facets_by_file,
                input_file=source_name,
                facets=[],
            )

            # read in as pl.DataFrame, ensure non-empty
            if is_dataframe(data_source):
                df = to_polars(data_source)
                df = normalize_dates(
                    df,
                    [
                        c
                        for c in ("reference_date", "target_end_date")
                        if c in df.columns
                    ],
                    strings=True,
                )
                df = df.with_columns(
                    [
                        pl.col(c).cast(pl.String)
                        for c in MODEL_DATA_STRING_COLUMNS
                        if c in df.columns
                    ]
                )
            else:
                df = read_forecasts(data_source)
            if df.is_empty():
                if excluded_files is not None:
                    excluded_files.add(source_name)
                continue  # skip to next if empty (non-fatal)

            # check for required columns
            missing = set(REQUIRED_MODEL_DATA_COLUMNS) - set(df.columns)
            if missing:
                raise ValueError(
                    f"{model} data source {source_name} is missing columns: {missing}."
                )

            # datatype assertions, ensure these are read in as strings
            df = df.with_columns(
                pl.col("target", "horizon", "location", "output_type").cast(pl.String)
            )
            df = normalize_dates(df, ["reference_date"], strings=True)
            df = normalize_horizon_column(df)
            df = df.select(
                [c for c in df.columns if c in REQUIRED_MODEL_DATA_COLUMNS]
            ).with_columns(
                pl.lit(model).alias("model"),
                pl.lit(source_name).alias("_source_file"),
            )

            # keep only the requested target and report any others being excluded
            current_model_targets = set(df["target"])
            excluded_targets = sorted(current_model_targets - {target})
            if excluded_targets:
                record_filtered_facets(
                    filtered_facets_by_file=filtered_facets_by_file,
                    input_file=source_name,
                    facets=["target"],
                )
            df = df.filter(pl.col("target") == target)
            if df.is_empty():
                excluded_due_to_target.append(source_name)
                if excluded_files is not None:
                    excluded_files.add(source_name)
                continue

            # filter entries s.t. target_end_date only spans the eval start/end date
            df = normalize_dates(df, ["target_end_date"])
            if not df.is_empty():
                in_eval_range_mask = df["target_end_date"].is_between(
                    date_value(eval_start_date), date_value(eval_end_date)
                )
                if (~in_eval_range_mask).any():
                    record_filtered_facets(
                        filtered_facets_by_file=filtered_facets_by_file,
                        input_file=source_name,
                        facets=["target_end_date"],
                    )
                df = df.filter(in_eval_range_mask)
            if df.is_empty():
                excluded_due_to_eval_range.append(source_name)
                if excluded_files is not None:
                    excluded_files.add(source_name)
                continue

            # filter out only output_type == quantile
            df = df.filter(pl.col("output_type") == "quantile")
            if df.is_empty():
                raise ValueError(
                    f"{model} data source {source_name} has no entries with output_type 'quantile'."
                )
            df = df.drop("output_type")

            # do strict processing if it is a library challenge run
            # i.e., force every forecast unit combination to be present
            if strict_grid_validation_enabled:
                df = _filter_to_required_challenge_facets(
                    df=df,
                    model_name=model,
                    csv_name=source_name,
                    normalized_required_reference_dates=normalized_required_reference_dates,
                    normalized_required_locations=normalized_required_locations,
                    normalized_required_horizons=normalized_required_horizons,
                    filtered_facets_by_file=filtered_facets_by_file,
                )
                if df.is_empty():
                    excluded_due_to_challenge_facets.append(source_name)
                    if excluded_files is not None:
                        excluded_files.add(source_name)
                    continue
            # properly rename the columns that need to be renamed (moving into scoringutils conventions)
            df = df.rename({"output_type_id": "quantile_level", "value": "predicted"})

            # get list of locations
            locations = set(df["location"])
            global_locations_list.extend(list(locations))

            # add to model-level list of dfs
            processed_dfs.append(df)

        # ensure that there are ANY dfs in the list for that model
        if not processed_dfs:
            excluded_files_msg = (
                f" Excluded files with no target_end_date values in range: "
                f"{', '.join(excluded_due_to_eval_range)}."
                if excluded_due_to_eval_range
                else ""
            )
            excluded_target_files_msg = (
                " Excluded files with no rows for the requested target "
                f"[{target}]: {', '.join(excluded_due_to_target)}."
                if excluded_due_to_target
                else ""
            )
            excluded_challenge_facet_files_msg = (
                " Excluded files with no rows remaining after library challenge "
                f"facet filtering: {', '.join(excluded_due_to_challenge_facets)}."
                if excluded_due_to_challenge_facets
                else ""
            )
            raise ValueError(
                f"No valid data found for model '{model}' after filtering. "
                f"Ensure CSV or Parquet files contain the requested target [{target}] and valid hubverse "
                f"data with target_end_date values between {eval_start_date} and {eval_end_date}."
                f"{excluded_target_files_msg}{excluded_files_msg}"
                f"{excluded_challenge_facet_files_msg}"
            )

        # concatenate all dfs in processed_dfs for one model
        concatenated_df = pl.concat(processed_dfs, how="diagonal_relaxed")
        if strict_grid_validation_enabled:
            _validate_required_challenge_grid(
                df=concatenated_df,
                model_name=model,
                normalized_required_reference_dates=normalized_required_reference_dates,
                normalized_required_locations=normalized_required_locations,
                normalized_required_horizons=normalized_required_horizons,
            )
        # append to dictionary
        model_dict[model] = concatenated_df

    locations_list = list(set(global_locations_list))
    # get extra model data
    for extra_model in include_models:
        extra_model_locations = locations_list
        # Config-route alignment is performed after every included model has
        # been loaded, so removed and missing facets can be reported.
        extra_model_allowed_forecast_units = None
        if strict_grid_validation_enabled:
            extra_model_locations = list(normalized_required_locations)
            extra_model_allowed_forecast_units = None
        df = _extra_models(
            hub_path=hub_path,
            model_name=extra_model,
            eval_start_date=eval_start_date,
            eval_end_date=eval_end_date,
            target=target,
            locations=extra_model_locations,
            allowed_forecast_units=extra_model_allowed_forecast_units,
            required_reference_dates=required_reference_dates,
            required_locations=required_locations,
            required_horizons=required_horizons,
        )
        model_dict[extra_model] = df

    logger.info("Success ✅")
    return model_dict, locations_list
