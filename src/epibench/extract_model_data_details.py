"""Function to gather information about the model data to be scored."""

import logging
import pandas as pd

REQUIRED_MODEL_DATA_COLUMNS = ['reference_date', 'target', 'horizon', 'target_end_date', 'location', 'output_type', 'output_type_id', 'value']
logger = logging.getLogger(__name__)


def extract_model_data_details(
        model_info: dict, 
        eval_start_date: 
        str, eval_end_date: str, 
        target: str
    ) -> dict[str, pd.DataFrame]:
    """
    Iteratively pre-process model data; run more checks

    Args:
        - model_info: a dict where keys are model names and values are a list of paths to CSVs
        - eval_start_date: YYYY-MM-DD when evaluation should begin (inclusive)
        - eval_end_date: YYYY-MM-DD when evaluation should end (inclusive)
        - target: a str of the data target to be scored on (only one per run)

    Returns:
        A dict where keys are model names and values are pre-processed pd.DataFrames
    """
    global_locations_list = []
    model_dict = {}
    for model in model_info:
        processed_dfs = [] # keep a model-level list of all dfs
        for csv_path in model_info[model]:

            # read in as pd.DataFrame, ensure non-empty
            df = pd.read_csv(csv_path)
            if df.empty:
                logger.warning(f"Model {model} CSV data file {csv_path.name} is an empty file. Skipping to next CSV.")
                continue # skip to next if empty (non-fatal)

            # datatype assertions, ensure these are read in as strings
            df = df.astype(
                {'target': str,
                'horizon': str,
                'location': str,
                'output_type': str
                }
            )

            # check for required columns
            missing = set(REQUIRED_MODEL_DATA_COLUMNS) - set(df.columns)
            if missing:
                raise ValueError(f"{model} CSV data file {csv_path.name} is missing columns: {missing}.")

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
                raise ValueError(
                    f"No valid data found for model '{model}' after filtering. "
                    "Ensure CSV files contain valid hubverse data."
                )
        # concatenate all dfs in processed_dfs for one model
        concatenated_df = pd.concat(processed_dfs, ignore_index=True)
        # append to dictionary
        model_dict[model] = concatenated_df

    locations_list = list(set(global_locations_list))
    
    logger.info("Success ✅")
    return model_dict, locations_list
