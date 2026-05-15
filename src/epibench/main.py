"""Main execution script for scoring quantile forecasts with scoringutils WIS"""

import argparse
import logging
import pandas as pd

from validate_config import validate_config
from extract_model_data_details import extract_model_data_details
from ground_truth import GroundTruth
from scoring_bridge import ScoringBridge


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """
    Main execution function
    """
    parser = argparse.ArgumentParser(description = 'Score models over specified time frame using a config.')
    parser.add_argument("--config-path",
                        type=str,
                        required=False,
                        help="Absolute path to your YAML configuration file.")
    args = parser.parse_args()

    logger.info("Validating configuration file...")
    hub_path, evaluation_start_date, evaluation_end_date, model_info, output_path = validate_config(args.config_path)

    logger.info("Validating model data...")
    model_dict, target, locations_list = extract_model_data_details( # presently only handles one target
        model_info=model_info, 
        eval_start_date=evaluation_start_date, 
        eval_end_date=evaluation_end_date
    )

    logger.info("Retrieving and formatting ground truth data...")
    gto = GroundTruth(
        hub_path=hub_path, 
        target=target, 
        locations=locations_list, 
        eval_start_date=evaluation_start_date, 
        eval_end_date=evaluation_end_date
    ) # access the actual DataFrame with gto.gt

    # concat and merge
    df = pd.concat(model_dict.values(), ignore_index=True)
    df = df.merge(gto.gt, on=["target", "target_end_date", "location"]).drop(columns=['target'])

    # score! with scoringutils (R component)
    logging.info("Scoring model data...")
    scorer = ScoringBridge()
    try:
        scores = scorer.score_forecasts(df)
    except Exception as e:
        raise Exception(f"{e}")

    # save locally and end
    full_output_path = f"{output_path}/EpiBench_scores.csv"
    scores.to_csv(full_output_path, index=False, encoding='utf-8-sig')
    logger.info("File executed successfully to end 🎉.")
    logger.info(f"Output file at {full_output_path}")


if __name__ == "__main__":
    main()


