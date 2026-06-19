"""Start of the `score` pipeline."""

import logging
import pandas as pd

from .config import Config
from .extract_model_data_details import extract_model_data_details
from .ground_truth import GroundTruth
from .scoring_bridge import ScoringBridge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def score(config_path=None):
    """
    Main executionfunction for the epibench score pipeline.
    """
    # validate config
    logger.info("Validating config...")
    config_object = Config(config_path=config_path, pipeline="score")
    # can reference config info with:
    # .hub_path (Path)
    # .evaluation_start_date (str)
    # .evaluation_end_date (str)
    # .target (str)
    # .model_info (dict[model name: list[paths to all CSVs]])
    # .baseline_model (str)
    # .output_path (Path)

    logger.info("Validating model data...")
    model_dict, locations_list = extract_model_data_details(
        hub_path=config_object.hub_path,
        model_info=config_object.model_info,
        baseline_model=config_object.baseline_model,
        eval_start_date=config_object.evaluation_start_date,
        eval_end_date=config_object.evaluation_end_date,
        target=config_object.target
    )

    logger.info("Retrieving and formatting ground truth data...")
    gto = GroundTruth(
        hub_path=config_object.hub_path,
        target=config_object.target,
        locations=locations_list,
        eval_start_date=config_object.evaluation_start_date,
        eval_end_date=config_object.evaluation_end_date
    ) # access the actual DataFrame with gto.gt

    # concat and merge 
    df = pd.concat(model_dict.values(), ignore_index=True)
    df = df.merge(gto.gt, on=["target", "target_end_date", "location"]).drop(columns=['target'])

    # score! with scoringutils (R component)
    logging.info("Scoring model data...")
    scorer = ScoringBridge()
    scores = scorer.score_forecasts(df)
    
    # save locally and end
    full_output_path = f"{config_object.output_path}/EpiBench_scores.csv" #TODO a hashing moment for naming as well?
    scores.to_csv(full_output_path, index=False, encoding='utf-8-sig') #TODO, this will overwrite files. likely want to fix
    logger.info("File executed successfully to end 🎉.")
    logger.info(f"Output file at {full_output_path}")
