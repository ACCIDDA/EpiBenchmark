"""Function to gather information about the model data to be scored."""

import logging
from pathlib import Path

import pandas as pd
from hubdata import connect_hub

REQUIRED_MODEL_DATA_COLUMNS = ['reference_date', 'target', 'horizon', 'target_end_date', 'location', 'output_type', 'output_type_id', 'value']
logger = logging.getLogger(__name__)


def _format_missing_combinations(
        missing_df: pd.DataFrame,
        model_name: str,
    ) -> str:
    """
    Construct a human-readable error for missing challenge grid combinations.
    """

    grouped = (
        missing_df.groupby(["target_end_date", "location"])["horizon"]
        .agg(lambda horizons: sorted(set(horizons), key=lambda horizon: int(horizon) if str(horizon).isdigit() else str(horizon)))
        .reset_index()
    )

    details = [
        f"{row.target_end_date}, location {row.location}: missing horizons {', '.join(row.horizon)}"
        for row in grouped.itertuples(index=False)
    ]
    details_text = "\n".join(details)
    # return pretty error message
    return (
        f"Model '{model_name}' is missing {len(missing_df)} required "
        "target_end_date/location/horizon combination(s) for this library challenge.\n"
        "Every challenge target_end_date, location, and horizon combination must be present "
        "in the input model data before a scorecard can be generated.\n"
        f"{details_text}"
    )


def _validate_required_challenge_grid(
        df: pd.DataFrame,
        model_name: str,
        required_target_end_dates: list[str],
        required_locations: list[str],
        required_horizons: list[str],
    ) -> None:
    """
    Ensure all required challenge date/location/horizon combinations exist.
    For library challenges only.
    """
    normalized_required_dates = [
        pd.Timestamp(target_end_date).strftime("%Y-%m-%d")
        for target_end_date in required_target_end_dates
    ]
    normalized_required_locations = [str(location) for location in required_locations]
    normalized_required_horizons = [str(horizon) for horizon in required_horizons]

    expected = pd.MultiIndex.from_product(
        [
            normalized_required_dates,
            normalized_required_locations,
            normalized_required_horizons,
        ],
        names=["target_end_date", "location", "horizon"],
    ).to_frame(index=False)

    observed = (
        df.assign(target_end_date=df["target_end_date"].dt.strftime("%Y-%m-%d"))
        [["target_end_date", "location", "horizon"]]
        .drop_duplicates()
    )

    missing_df = expected.merge(
        observed,
        on=["target_end_date", "location", "horizon"],
        how="left",
        indicator=True,
    )
    missing_df = missing_df[missing_df["_merge"] == "left_only"].drop(columns="_merge")
    # if there are missing combinations
    if not missing_df.empty:
        raise ValueError(_format_missing_combinations(missing_df, model_name))


def _extra_models(
        hub_path: Path,
        model_name: str,
        eval_start_date: str,
        eval_end_date: str,
        target: str,
        locations: list[str]
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
        required_target_end_dates: list[str] | None = None,
        required_locations: list[str] | None = None,
        required_horizons: list[str] | None = None,
    ) -> tuple[dict[str, pd.DataFrame], list[str]]:
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
        required_target_end_dates: Required target_end_dates for strict
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
            required_target_end_dates,
            required_locations,
            required_horizons,
        )
    )

    global_locations_list = []
    model_dict = {}
    for model in model_info:

        # pathway for their specified model data
        processed_dfs = [] # keep a model-level list of all dfs
        excluded_due_to_eval_range = []
        for csv_path in model_info[model]:

            # read in as pd.DataFrame, ensure non-empty
            df = pd.read_csv(csv_path)
            if df.empty:
                logger.warning(f"Model {model} CSV data file {csv_path.name} is an empty file. Skipping to next CSV.")
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

            # target enforcements
            current_model_target_s = set(df['target'])
            # ensure there is only 1 per model csv
            if len(current_model_target_s) > 1:
                raise ValueError(
                    f"{model} CSV data file {csv_path.name} `target` column has more than one unique value. "
                    f"Currently, `epibench score` only handles model data with a single unique target."
                )
            else:
                # ensure the single target found matches the one in config
                current_model_target = next(iter(current_model_target_s))
                if current_model_target != target:
                    raise ValueError(
                        f"The target ({current_model_target}) found in {model} CSV data file {csv_path.name} "
                        f"does not match the target specified in config ({target})."
                    )
            
            # filter entries s.t. target_end_date only spans the eval start/end date 
            df['target_end_date'] = pd.to_datetime(df['target_end_date'])
            df = df[df['target_end_date'].between(eval_start_date, eval_end_date)]
            if df.empty:
                excluded_due_to_eval_range.append(csv_path.name)
                logger.info(
                    f"Model {model} CSV data file {csv_path.name} has no target_end_date values "
                    f"between eval start date {eval_start_date} and eval end date {eval_end_date}. "
                    "Excluding it from scoring."
                )
                continue

            # filter out only output_type == quantile
            df = df[df['output_type'] == 'quantile']
            if df.empty:
                raise ValueError(f"{model} CSV data file {csv_path.name} has no entries with output_type 'quantile'.")
            df = df.drop(columns=['output_type'])

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
                raise ValueError(
                    f"No valid data found for model '{model}' after filtering. "
                    f"Ensure CSV files contain valid hubverse data with target_end_date values "
                    f"between {eval_start_date} and {eval_end_date}.{excluded_files_msg}"
                )
        if excluded_due_to_eval_range:
            logger.info(
                f"Excluded {len(excluded_due_to_eval_range)} file(s) for model {model} because "
                f"they had no target_end_date values in the evaluation range: "
                f"{', '.join(excluded_due_to_eval_range)}"
            )
        # concatenate all dfs in processed_dfs for one model
        concatenated_df = pd.concat(processed_dfs, ignore_index=True)
        if strict_grid_validation_enabled:
            _validate_required_challenge_grid(
                df=concatenated_df,
                model_name=model,
                required_target_end_dates=required_target_end_dates,
                required_locations=required_locations,
                required_horizons=required_horizons,
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
            locations=locations_list
        )
        model_dict[extra_model] = df
    
    logger.info("Success ✅")
    return model_dict, locations_list
