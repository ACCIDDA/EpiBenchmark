"""Function to gather information about the model data to be scored."""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

import pandas as pd
from hubdata import connect_hub

from .horizon_utils import sort_horizon_strings
from .scoring_summary import record_filtered_facets

REQUIRED_MODEL_DATA_COLUMNS = ['reference_date', 'target', 'horizon', 'target_end_date', 'location', 'output_type', 'output_type_id', 'value']
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
        pd.Timestamp(reference_date).strftime("%Y-%m-%d")
        for reference_date in required_reference_dates
    }
    normalized_required_locations = {str(location) for location in required_locations}
    normalized_required_horizons = {str(horizon) for horizon in required_horizons}
    return (
        normalized_required_reference_dates,
        normalized_required_locations,
        normalized_required_horizons,
    )


def _filter_to_required_challenge_facets(
        df: pd.DataFrame,
        model_name: str,
        csv_name: str,
        normalized_required_reference_dates: Set[str],
        normalized_required_locations: Set[str],
        normalized_required_horizons: Set[str],
        filtered_facets_by_file: Optional[Dict[str, Set[str]]] = None,
    ) -> pd.DataFrame:
    """
    Given reference_dates, locations, and horizons lists specified in the library challenge,
    filter out any excess values found and record them for summary output.
    """

    # normalize everything to be a string, build masks to filter with
    reference_date_strings = pd.to_datetime(df["reference_date"], errors="raise").dt.strftime("%Y-%m-%d")
    reference_date_mask = reference_date_strings.isin(normalized_required_reference_dates)
    location_mask = df["location"].isin(normalized_required_locations)
    horizon_mask = df["horizon"].isin(normalized_required_horizons)
    keep_mask = reference_date_mask & location_mask & horizon_mask

    # filter, record extras that were found
    excluded_df = df.loc[~keep_mask].copy()
    if not excluded_df.empty:
        excluded_reference_dates = sorted(
            set(
                reference_date_strings.loc[
                    excluded_df.index[
                        ~reference_date_strings.loc[excluded_df.index].isin(
                            normalized_required_reference_dates
                        )
                    ]
                ]
            )
        )
        excluded_locations = sorted(
            set(
                excluded_df.loc[
                    ~excluded_df["location"].isin(normalized_required_locations),
                    "location",
                ]
            )
        )
        excluded_horizons = sort_horizon_strings(
            set(
                excluded_df.loc[
                    ~excluded_df["horizon"].isin(normalized_required_horizons),
                    "horizon",
                ]
            )
        )

        filtered_facet_names = []
        if excluded_reference_dates:
            filtered_facet_names.append("reference_date")
        if excluded_locations:
            filtered_facet_names.append("location")
        if excluded_horizons:
            filtered_facet_names.append("horizon")
        record_filtered_facets(
            filtered_facets_by_file=filtered_facets_by_file,
            input_file=csv_name,
            facets=filtered_facet_names,
        )

    return df.loc[keep_mask].copy()


def _validate_required_challenge_grid(
        df: pd.DataFrame,
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
    expected = pd.DataFrame(expected_rows)

    observed = (
        df.assign(
            reference_date=pd.to_datetime(df["reference_date"], errors="raise").dt.strftime("%Y-%m-%d"),
        )
        [["reference_date", "location", "horizon"]]
        .drop_duplicates()
    )

    missing_df = expected.merge(
        observed,
        on=["reference_date", "location", "horizon"],
        how="left",
        indicator=True,
    )
    missing_df = missing_df[missing_df["_merge"] == "left_only"].drop(columns="_merge")
    # if there are missing combinations
    if not missing_df.empty:
        # return a pretty message
        def _format_missing_combinations() -> str:
            """Construct a human-readable error for missing facet combinations."""
            grouped = (
                missing_df.groupby(["reference_date", "location"])["horizon"]
                .agg(
                    lambda horizons: sort_horizon_strings(list(horizons))
                )
                .reset_index()
            )
            details = [
                f"{row.reference_date}, location {row.location}: missing horizons {', '.join(row.horizon)}"
                for row in grouped.itertuples(index=False)
            ]
            details_text = "\n".join(details)
            return (
                f"Model '{model_name}' is missing {len(missing_df)} required "
                "forecast unit combination(s) for this library challenge.\n"
                "Every required reference_date/location/horizon forecast unit "
                "must be present in the input model data before a scorecard can be generated.\n"
                f"{details_text}"
            )

        raise ValueError(_format_missing_combinations())


def _extra_models(
        hub_path: Path,
        model_name: str,
        eval_start_date: str,
        eval_end_date: str,
        target: str,
        locations: List[str],
        required_reference_dates: Optional[List[str]] = None,
        required_locations: Optional[List[str]] = None,
        required_horizons: Optional[List[str]] = None,
    ) -> pd.DataFrame:
    """
    write
    """
    # use hubdata connect_hub() to quickly pull extra model data
    try:
        hub_connection = connect_hub(hub_path=hub_path)
        data_return = hub_connection.get_dataset().to_table().to_pandas()
    except Exception as e:
        raise ConnectionError(
            f"Could not establish connection to hub {hub_path} to retrieve extra "
            f"model ({model_name}) data. Error: {e}"
        )
    # filter for the things we need
    data_return['target_end_date'] = pd.to_datetime(data_return['target_end_date'])
    df = data_return[
                (data_return['model_id'] == model_name) & 
                (data_return['target_end_date'].between(eval_start_date, eval_end_date)) & 
                (data_return['target'] == target) & 
                (data_return['output_type'] == 'quantile') &
                (data_return['location'].isin(locations))
            ]
    if df.empty:
        raise ValueError(
            f"Could not find model quantile data for model {model_name} "
            f"for target '{target}' between dates {eval_start_date.date()} and {eval_end_date.date()}. "
            f"Searched for locations found in provided model data: {locations}"
        )

    # Match the user CSV path by normalizing challenge facet columns to strings.
    df = df.astype(
        {
            "reference_date": str,
            "horizon": str,
            "location": str,
        }
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

    # column renaming
    df = df.rename(columns={'model_id': 'model', 'output_type_id': 'quantile_level', 'value': 'predicted'})

    return df


def extract_model_data_details(
        hub_path: Path,
        model_info: dict, 
        include_models: list,
        eval_start_date: str, 
        eval_end_date: str, 
        target: str,
        required_reference_dates: Optional[List[str]] = None,
        required_locations: Optional[List[str]] = None,
        required_horizons: Optional[List[str]] = None,
        filtered_facets_by_file: Optional[Dict[str, Set[str]]] = None,
        excluded_files: Optional[Set[str]] = None,
    ) -> Tuple[Dict[str, pd.DataFrame], List[str]]:
    """
    Iteratively pre-process model data; run more checks

    Args:
        hub_path: A Path to the hub corresponding to model data.
        model_info: A dict where keys are model names and values are lists of
            paths to CSV files.
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
            `pandas.DataFrame` objects.
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
        processed_dfs = [] # keep a model-level list of all dfs
        excluded_due_to_eval_range = []
        excluded_due_to_target = []
        excluded_due_to_challenge_facets = []
        for csv_path in model_info[model]:
            record_filtered_facets(
                filtered_facets_by_file=filtered_facets_by_file,
                input_file=csv_path.name,
                facets=[],
            )

            # read in as pd.DataFrame, ensure non-empty
            df = pd.read_csv(csv_path, dtype=MODEL_DATA_STRING_COLUMNS)
            if df.empty:
                if excluded_files is not None:
                    excluded_files.add(csv_path.name)
                continue # skip to next if empty (non-fatal)

            # check for required columns
            missing = set(REQUIRED_MODEL_DATA_COLUMNS) - set(df.columns)
            if missing:
                raise ValueError(f"{model} CSV data file {csv_path.name} is missing columns: {missing}.")

            # datatype assertions, ensure these are read in as strings
            df = df.astype(
                {'target': str,
                'horizon': str,
                'location': str,
                'output_type': str
                }
            )

            # drop all other columns (we don't use them in this package)
            to_drop = [col for col in df.columns if col not in REQUIRED_MODEL_DATA_COLUMNS]
            df = df.drop(columns=to_drop)

            # add column for model name (`model`)
            df['model'] = model 
            df["_source_file"] = csv_path.name

            # keep only the requested target and report any others being excluded
            current_model_targets = set(df["target"])
            excluded_targets = sorted(current_model_targets - {target})
            if excluded_targets:
                record_filtered_facets(
                    filtered_facets_by_file=filtered_facets_by_file,
                    input_file=csv_path.name,
                    facets=["target"],
                )
            df = df[df["target"] == target].copy()
            if df.empty:
                excluded_due_to_target.append(csv_path.name)
                if excluded_files is not None:
                    excluded_files.add(csv_path.name)
                continue
            
            # filter entries s.t. target_end_date only spans the eval start/end date 
            df['target_end_date'] = pd.to_datetime(df['target_end_date'])
            if not df.empty:
                in_eval_range_mask = df['target_end_date'].between(eval_start_date, eval_end_date)
                if (~in_eval_range_mask).any():
                    record_filtered_facets(
                        filtered_facets_by_file=filtered_facets_by_file,
                        input_file=csv_path.name,
                        facets=["target_end_date"],
                    )
                df = df[in_eval_range_mask]
            if df.empty:
                excluded_due_to_eval_range.append(csv_path.name)
                if excluded_files is not None:
                    excluded_files.add(csv_path.name)
                continue

            # filter out only output_type == quantile
            df = df[df['output_type'] == 'quantile']
            if df.empty:
                raise ValueError(f"{model} CSV data file {csv_path.name} has no entries with output_type 'quantile'.")
            df = df.drop(columns=['output_type'])

            # do strict processing if it is a library challenge run 
            # i.e., force every forecast unit combination to be present
            if strict_grid_validation_enabled:
                df = _filter_to_required_challenge_facets(
                    df=df,
                    model_name=model,
                    csv_name=csv_path.name,
                    normalized_required_reference_dates=normalized_required_reference_dates,
                    normalized_required_locations=normalized_required_locations,
                    normalized_required_horizons=normalized_required_horizons,
                    filtered_facets_by_file=filtered_facets_by_file,
                )
                if df.empty:
                    excluded_due_to_challenge_facets.append(csv_path.name)
                    if excluded_files is not None:
                        excluded_files.add(csv_path.name)
                    continue
            # properly rename the columns that need to be renamed (moving into scoringutils conventions)
            df = df.rename(columns={'output_type_id': 'quantile_level', 'value': 'predicted'})

            # get list of locations
            locations = set(df['location']) 
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
                    f"Ensure CSV files contain the requested target [{target}] and valid hubverse "
                    f"data with target_end_date values between {eval_start_date} and {eval_end_date}."
                    f"{excluded_target_files_msg}{excluded_files_msg}"
                    f"{excluded_challenge_facet_files_msg}"
                )
        
        # concatenate all dfs in processed_dfs for one model
        concatenated_df = pd.concat(processed_dfs, ignore_index=True)
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
        df = _extra_models(
            hub_path=hub_path,
            model_name=extra_model,
            eval_start_date=eval_start_date,
            eval_end_date=eval_end_date,
            target=target,
            locations=locations_list,
            required_reference_dates=required_reference_dates,
            required_locations=required_locations,
            required_horizons=required_horizons,
        )
        model_dict[extra_model] = df
    
    logger.info("Success ✅")
    return model_dict, locations_list
