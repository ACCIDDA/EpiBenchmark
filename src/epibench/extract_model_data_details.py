"""Function to gather information about the model data to be scored."""

import logging
import pandas as pd

REQUIRED_MODEL_DATA_COLUMNS = ['target', 'horizon', 'target_end_date', 'location', 'output_type', 'output_type_id', 'value']
logger = logging.getLogger(__name__)


def extract_model_data_details(model_info: dict, eval_start_date, eval_end_date) -> dict:
    """
    Iteratively extract info from and pre-process model data.

    general `model_info` structure is: 
    {"model1": "/path/to/model1data.csv", "model2": "/path/to/model2data.csv", "model3": "/path/to/model3data.csv"} 
    """
    global_target_list = []
    global_locations_list = []
    return_dict = {}
    for model in model_info:

        # read in as pd.DataFrame
        df = pd.read_csv(model_info[model])

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
        assert not missing, f"{model} CSV data is missing columns: {missing}"

        # drop all other columns (we don't use them in this package)
        to_drop = [col for col in df.columns if col not in REQUIRED_MODEL_DATA_COLUMNS]
        df = df.drop(columns=to_drop)

        # add column for model name (`model`)
        df['model'] = model 

        # record target, enforce that there's only 1 
        target = set(df['target'])
        if len(target) > 1:
            raise ValueError(
                f"{model} CSV data `target` column has more than one unique value. "
                f"Currently, EpiBench only handles model data with one unique target per run."
            )
        current_target = list(target)[0]
        global_target_list.append(str(current_target))
        
        # filter entries s.t. target_end_date only spans the eval start/end date 
        df['target_end_date'] = pd.to_datetime(df['target_end_date'])
        df = df[df['target_end_date'].between(eval_start_date, eval_end_date)]

        # filter out only output_type == quantile
        df = df[df['output_type'] == 'quantile']
        assert not df.empty, f"{model} CSV data has no entries with output_type 'quantile'."

        # properly rename the columns that need to be renamed (moving into scoringutils conventions)
        df = df.rename(columns={'output_type_id': 'quantile_level', 'value': 'predicted'})

        # get list of locations
        locations = set(df['location']) 
        global_locations_list.extend(list(locations))

        # append to dictionary
        return_dict[model] = {"target": target, "locations": locations}
    
    # prepare other info for return
    if len(set(global_target_list)) > 1:
        raise ValueError(
            f"Found more than one target in your model data: {global_target_list}. Please consolidate to one unified target per run."
        )
    else:
        singular_target = str(global_target_list[0])
    locations_list = list(set(global_locations_list))
    
    logger.info("Success ✅")
    return return_dict, singular_target, locations_list