"""Function to get model data for models with 'complete' challenge satisfaction, prepare for scoring."""

import logging
from pathlib import Path

import polars as pl

from .dataframes import to_polars, normalize_dates, date_value
from hubdata import connect_hub

from .scoring_ground_truth import ScoringGroundTruth

logger = logging.getLogger(__name__)


def _add_ground_truth_for_scoring(
    hub_path: Path, model_df: pl.DataFrame
) -> pl.DataFrame:
    """
    Add an `observed` column to processed model data by matching forecast
    units with ground truth data retrieved via ScoringGroundTruth class.
    """

    # establish facets
    locations = sorted({str(location) for location in model_df["location"]})
    target = str(model_df["target"][0])
    eval_start_date = normalize_dates(model_df, ["target_end_date"])[
        "target_end_date"
    ].min()
    eval_end_date = normalize_dates(model_df, ["target_end_date"])[
        "target_end_date"
    ].max()

    # initialize `gto` object
    gto = ScoringGroundTruth(
        hub_path=hub_path,
        target=target,
        locations=locations,
        eval_start_date=eval_start_date,
        eval_end_date=eval_end_date,
    )

    # match with model_df, return
    return model_df.join(
        gto.gt,
        on=["target", "target_end_date", "location"],
        how="left",
        maintain_order="left",
        nulls_equal=True,
    ).drop("target")


def prep_complete_models_for_plotting(
    hub_path: Path,
    complete_models: list[str],
    baseline_model: str,
    valid_locations: list[str],
    valid_quantiles: list[str],
    valid_horizons: list[str],
    valid_reference_dates: list[str],
    valid_target: str,
) -> pl.DataFrame:
    """
    For complete models found in a challenge definition, fetch their
    model data from a Hubdata hub connection, appropriately filter to
    match the challenge, and put into scoringutils format.

    Args:
        - hub_path: Path to the corresponding hub
        - baseline_model: baseline model for the hub
        - complete_models: list of models for which challenge completion has been satisfied
        - + All forecast unit facets + quantiles defined in the challenge JSON (locations, horizons, reference_dates, output_type_ids, target)

    Returns:
        A pl.DataFrame ready to enter scoringutils
    """

    full_hub_df = pl.from_arrow(connect_hub(hub_path=hub_path).to_table())
    logger.info("Hub connection established.")
    full_hub_df = normalize_dates(
        to_polars(full_hub_df), ["reference_date", "target_end_date"]
    )
    full_hub_df = full_hub_df.with_columns(
        pl.col("location", "output_type_id").cast(pl.String),
        pl.col("horizon").cast(pl.Float64),
    )
    models = list(dict.fromkeys([*complete_models, baseline_model]))
    df = full_hub_df.filter(
        pl.col("model_id").is_in(models)
        & pl.col("reference_date").is_in([date_value(d) for d in valid_reference_dates])
        & pl.col("horizon").is_in([float(h) for h in valid_horizons])
        & (pl.col("target") == valid_target)
        & (pl.col("output_type") == "quantile")
        & pl.col("output_type_id").is_in(valid_quantiles)
        & pl.col("location").is_in(valid_locations)
    ).rename(
        {"model_id": "model", "output_type_id": "quantile_level", "value": "predicted"}
    )
    # Preserve the requested model order without filtering the whole table repeatedly.
    df = (
        df.with_columns(
            pl.col("model")
            .replace_strict({m: i for i, m in enumerate(models)})
            .alias("_order")
        )
        .sort("_order", maintain_order=True)
        .drop("_order")
    )
    df = df.with_columns(pl.col("horizon").cast(pl.String))
    df = _add_ground_truth_for_scoring(hub_path=hub_path, model_df=df)
    df = normalize_dates(df, ["target_end_date"], strings=True)
    logger.info("Success ✅")
    return df
