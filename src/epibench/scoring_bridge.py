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
                f"Failed to import R packages. Ensure R and 'scoringutils' are installed. Error: {e}"
            )

    def score_forecasts(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Method to convert Python objects to required R variables, then generate and return scores.
        """

        with localconverter(robjects.default_converter + pandas2ri.converter):
            # convert Python objects to R objects
            r_data = pandas2ri.py2rpy(data)
            forecast_unit = robjects.StrVector(["target_end_date", "location", "horizon", "model"])

            forecast_object = self.scoringutils.as_forecast_quantile(r_data, forecast_unit=forecast_unit)
            scores = self.scoringutils.score(forecast_object)

            back_to_python_data = pandas2ri.rpy2py(scores)
            
        logging.info("Success ✅")
        return back_to_python_data
