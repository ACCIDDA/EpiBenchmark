"""Registry for ad hoc scorecard metric functions."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

import pandas as pd


ScorecardMetric = Callable[[pd.DataFrame], Any]


def total_wis(score_file: pd.DataFrame) -> Any:
    """Total (sum) of WIS across all locations, target end dates, horizons."""
    pass


def coverage_50(score_file: pd.DataFrame) -> Any:
    """Average 50% interval coverage across all locations, target end dates, horizons."""
    pass


def coverage_90(score_file: pd.DataFrame) -> Any:
    """Average 90% interval coverage across all locations, target end dates, horizons."""
    pass


SCORECARD_FUNCTIONS: dict[str, ScorecardMetric] = {
    "total wis": total_wis,
    "50_coverage": coverage_50,
    "90_coverage": coverage_90,
}


def custom_scorecard(
    scorecard_function_names: Iterable[str], score_file: pd.DataFrame
) -> dict[str, Any]:
    """Execute the configured scorecard functions and return results by name."""
    results: dict[str, Any] = {}

    for function_name in scorecard_function_names:
        try:
            scorecard_function = SCORECARD_FUNCTIONS[function_name]
        except KeyError as exc:
            raise ValueError(
                f"Unknown scorecard function requested: {function_name}"
            ) from exc

        results[function_name] = scorecard_function(score_file)

    return results
