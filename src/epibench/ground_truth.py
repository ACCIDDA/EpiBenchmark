"""Class for ground truth data that corresponds to the model data to be scored"""


import pandas as pd
import logging
from hubdata import connect_target_data
from hubdata.create_target_data_schema import TargetType


logger = logging.getLogger(__name__)
# these columns can be dropped after processing has occurred
COLUMNS_TO_DROP = ['weekly_rate', 'location_name', 'as_of'] 


class GroundTruth:
    def __init__(self, hub_path: str, target: str, locations: list, eval_start_date: str, eval_end_date: str):
        """
        Initialization of the GroundTruth class. Pulls directly from a hub local clone using hubdata package.
        Limited validation required.
        """
        self.target = target
        self.locations = locations
        self.start_date = eval_start_date
        self.end_date = eval_end_date
        self._process_ground_truth_data(hub_path=hub_path)

    def _process_ground_truth_data(self, hub_path: str):
        """Process the ground truth data such that it only contains the info we need"""
        self.gt = self._filter_gt(
            connect_target_data(hub_path=hub_path, target_type=TargetType.TIME_SERIES).to_table().to_pandas()
        ) # TODO, maybe should clean NAs from here? idk how scoringutils handles them
        logger.info("Success ✅")

    def _filter_gt(self, gt: pd.DataFrame) -> pd.DataFrame:
        """
        Apply filters/processing to the ground truth data retreived from hub

        - only dates we need for evaluation are kept
        - only target and locations we need are kept
        - only most recent as_of value is kept
        - rename `observation` column as `observed`
        - drop columns we don't need
        """
        # ensure correct data type for date columns
        gt['target_end_date'] = pd.to_datetime(gt['target_end_date'], errors='coerce')
        gt['as_of'] = pd.to_datetime(gt['as_of'], errors='coerce')
        # only keep the target we need
        gt = gt[gt['target'] == self.target].copy()
        assert not gt.empty, f"Ground truth data fetched from provided hub does not have target '{self.target}'"
        
        gt = gt[gt['location'].isin(self.locations)].copy()
        assert not gt.empty, f"Ground truth data fetched from provided hub does not have locations {self.locations} for target {self.target}"

        gt = gt[gt['target_end_date'].between(self.start_date, self.end_date)].copy()
        assert not gt.empty, "Ground truth data fetched from provided hub does not have any data for target, locations, dates combo found in model data."

        # as_of filtering 
        gt.sort_values(by='as_of', ascending=True, inplace=True)
        gt.drop_duplicates(
            subset=["target_end_date", "location", "target"],
            keep="last",
            inplace=True
        )

        # rename `observation` to `observed`
        gt = gt.rename(columns={'observation': 'observed'})

        gt = gt.drop(columns=COLUMNS_TO_DROP)
        return gt