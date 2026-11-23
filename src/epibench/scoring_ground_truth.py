"""Scoring-time ground truth data prepared to match model outputs."""

import polars as pl

from .dataframes import to_polars, normalize_dates, date_value
import logging
from pathlib import Path
from hubdata import connect_target_data
from hubdata.create_target_data_schema import TargetType

from .create_ground_truth import _suppress_missing_target_data_schema_warning


logger = logging.getLogger(__name__)
# these columns can be dropped after processing has occurred
COLUMNS_TO_KEEP = ["observed", "target_end_date", "location", "target"]


class ScoringGroundTruth:
    def __init__(
        self,
        hub_path: Path,
        target: str,
        locations: list,
        eval_start_date: str,
        eval_end_date: str,
    ):
        """
        Initialize ScoringGroundTruth from a local hub clone using hubdata.
        Limited validation required.
        """
        self.target = target
        self.locations = locations
        self.start_date = eval_start_date
        self.end_date = eval_end_date
        self._process_ground_truth_data(hub_path=hub_path)

    def _process_ground_truth_data(self, hub_path: Path):
        """Process the ground truth data such that it only contains the info we need"""
        suppress_hubdata_warning = not (
            hub_path / "hub-config" / "target-data.json"
        ).is_file()
        with _suppress_missing_target_data_schema_warning(
            enabled=suppress_hubdata_warning
        ):
            gt = pl.from_arrow(
                connect_target_data(
                    hub_path=hub_path,
                    target_type=TargetType.TIME_SERIES,
                ).to_table()
            )
        self.gt = self._filter_gt(
            gt
        )  # TODO, maybe should clean NAs from here? idk how scoringutils handles them
        logger.info("Success ✅")

    def _filter_gt(self, gt: pl.DataFrame) -> pl.DataFrame:
        """
        Apply filters/processing to the ground truth data retreived from hub

        - only dates we need for evaluation are kept
        - only target and locations we need are kept
        - only most recent as_of value is kept
        - rename `observation` column as `observed`
        - drop columns we don't need
        """
        # ensure correct data type for date columns
        gt = normalize_dates(
            to_polars(gt), ["target_end_date", "as_of"], strict=False
        ).with_columns(pl.col("location").cast(pl.String))
        # only keep the target we need
        gt = gt.filter(pl.col("target") == self.target)
        assert (
            not gt.is_empty()
        ), f"Ground truth data fetched from provided hub does not have target '{self.target}'"

        gt = gt.filter(pl.col("location").is_in(self.locations))
        assert (
            not gt.is_empty()
        ), f"Ground truth data fetched from provided hub does not have locations {self.locations} for target {self.target}"

        gt = gt.filter(
            pl.col("target_end_date").is_between(
                date_value(self.start_date), date_value(self.end_date)
            )
        )
        assert (
            not gt.is_empty()
        ), "Ground truth data fetched from provided hub does not have any data for target, locations, dates combo found in model data."

        # as_of filtering
        gt = gt.sort("as_of", nulls_last=True, maintain_order=True).unique(
            subset=["target_end_date", "location", "target"],
            keep="last",
            maintain_order=True,
        )

        # rename `observation` to `observed`
        gt = gt.rename({"observation": "observed"})

        missing_columns = set(COLUMNS_TO_KEEP) - set(gt.columns)
        if missing_columns:
            raise ValueError(
                "Ground truth data is missing columns required for scoring: "
                f"{sorted(missing_columns)}."
            )
        gt = gt.select(COLUMNS_TO_KEEP)

        if gt["observed"].is_null().any():
            na_info = gt.filter(pl.col("observed").is_null())
            logger.warning(
                f"\nWARNING: NA observed value found in hub ground truth data for scoring:\n{na_info}\nThese units will be excluded from scoring.\n"
            )

        return gt
