"""Registry for ad hoc scorecard metric functions."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

import polars as pl

from .dataframes import to_polars


ScorecardMetric = Callable[[pl.DataFrame], Any]


def total_wis(score_file: pl.DataFrame) -> Any:
    """Total (sum) of WIS across all locations, target end dates, horizons."""
    return to_polars(score_file)["wis"].sum()


def coverage_50(score_file: pl.DataFrame) -> Any:
    """Average 50% interval coverage across all locations, target end dates, horizons."""
    return to_polars(score_file)["interval_coverage_50"].cast(pl.Float64).mean()


def coverage_95(score_file: pl.DataFrame) -> Any:
    """Average 95% interval coverage across all locations, target end dates, horizons."""
    return to_polars(score_file)["interval_coverage_95"].cast(pl.Float64).mean()


SCORECARD_FUNCTIONS: dict[str, ScorecardMetric] = {
    "total wis": total_wis,
    "50_coverage": coverage_50,
    "95_coverage": coverage_95,
}


def custom_scorecard(
    model_name: str, scorecard_function_names: Iterable[str], score_file: pl.DataFrame
) -> dict[str, Any]:
    """Execute the configured scorecard functions and return results by name."""

    results: dict[str, Any] = {}
    # filter out anything besides the single model submitted
    score_file = to_polars(score_file).filter(pl.col("model") == model_name)

    # run all the functions we need for the scorecard
    for function_name in scorecard_function_names:
        try:
            scorecard_function = SCORECARD_FUNCTIONS[function_name]
        except KeyError as exc:
            raise ValueError(
                f"Unknown scorecard function requested: {function_name}"
            ) from exc

        results[function_name] = scorecard_function(score_file)

    return results
