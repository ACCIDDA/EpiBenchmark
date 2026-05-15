"""Bridge between Python package and R scoringutils functionality."""

import pandas as pd
import rpy2.robjects as robjects
from rpy2.robjects import pandas2ri
from rpy2.robjects.packages import importr
from rpy2.robjects.conversion import localconverter
import logging

logger = logging.getLogger(__name__)

class ScoringBridge:
    def __init__(self):
        try:
            self.scoringutils = importr('scoringutils')
            self.base = importr('base')
        except Exception as e:
            raise ImportError(
                f"Failed to load R environment. Error: {e}"
            )

    def score_forecasts(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Scores forecast data using scoringutils (R).
        """
        unit_cols = ["target_end_date", "location", "horizon", "model"]
        for col in unit_cols:
            if col in data.columns:
                data[col] = data[col].astype(str)

        with localconverter(robjects.default_converter + pandas2ri.converter):
            robjects.r.assign("input_df", data)
            robjects.r.assign("units", robjects.StrVector(unit_cols))
            r_logic = """
            library(scoringutils)
            # Create the object and immediately score it without returning to Python
            forecast_obj <- as_forecast_quantile(
                input_df, 
                forecast_unit = units
            )
            results <- score(forecast_obj)
            results
            """
            
            try:
                r_scores = robjects.r(r_logic)
                if isinstance(r_scores, pd.DataFrame):
                    logger.info("Success ✅")
                    return r_scores
                logger.info("Success ✅")
                return robjects.conversion.rpy2py(r_scores)
            except Exception as e:
                logger.error(f"R-side scoring failed: {e}")
                raise
