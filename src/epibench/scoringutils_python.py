"""Fast Python implementation of the quantile scoringutils metrics EpiBench uses.

The formulas and grouping behavior in this module mirror scoringutils 2.2.0.9000
for the metric list historically configured in :mod:`epibench.scoring_bridge`.
They are deliberately kept private to EpiBench rather than presented as a
general Python port of scoringutils.
"""

from __future__ import annotations

import logging
import warnings
from collections.abc import Sequence

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ForecastValidationError(ValueError):
    """Forecast data cannot be scored safely."""


class MetricScoringWarning(UserWarning):
    """One metric could not be calculated while scoring continued."""


FORECAST_UNIT_COLUMNS = [
    "model",
    "reference_date",
    "target_end_date",
    "location",
    "horizon",
]
REQUIRED_COLUMNS = ["observed", "predicted", "quantile_level"]
SCORE_COLUMNS = [
    "wis",
    "overprediction",
    "underprediction",
    "dispersion",
    "bias",
    "interval_coverage_50",
    "interval_coverage_95",
    "ae_median",
]


def _check_columns(data: pd.DataFrame) -> None:
    if not isinstance(data, pd.DataFrame):
        raise ForecastValidationError("Forecast data must be a pandas DataFrame.")
    if data.empty:
        raise ForecastValidationError("Forecast data must contain at least one row.")
    if "sample_id" in data.columns and "quantile_level" in data.columns:
        raise ForecastValidationError(
            "Forecast data cannot contain both `quantile_level` and `sample_id`."
        )
    missing = [
        column
        for column in [*FORECAST_UNIT_COLUMNS, *REQUIRED_COLUMNS]
        if column not in data.columns
    ]
    if missing:
        raise ForecastValidationError(
            f"Forecast data is missing required columns: {missing}"
        )


def _prepare_forecasts(data: pd.DataFrame) -> pd.DataFrame:
    """Match as_forecast_quantile(), set_forecast_unit(), and clean_forecast()."""
    _check_columns(data)
    columns = [*REQUIRED_COLUMNS, *FORECAST_UNIT_COLUMNS]
    forecast = data.loc[:, columns].copy()
    # clean_forecast(na.omit = TRUE) considers every input column, including
    # extra metadata columns that are not used by the metrics.
    missing_rows = data.isna().any(axis=1).to_numpy()

    for column in REQUIRED_COLUMNS:
        if pd.api.types.is_bool_dtype(forecast[column]):
            raise ForecastValidationError(
                f"Forecast column '{column}' must be numeric."
            )
        try:
            forecast[column] = pd.to_numeric(forecast[column], errors="raise")
        except (TypeError, ValueError) as error:
            raise ForecastValidationError(
                f"Forecast column '{column}' must be numeric."
            ) from error
        if pd.api.types.is_bool_dtype(forecast[column]):
            raise ForecastValidationError(
                f"Forecast column '{column}' must be numeric."
            )

    quantiles = forecast["quantile_level"].to_numpy(dtype=np.float64, copy=False)
    finite_quantiles = quantiles[~np.isnan(quantiles)]
    if np.any((finite_quantiles < 0) | (finite_quantiles > 1)):
        raise ForecastValidationError(
            "Quantile levels must be between 0 and 1 inclusive."
        )

    unique_quantiles = np.unique(finite_quantiles)
    if unique_quantiles.size > 1 and np.any(np.diff(unique_quantiles) <= 1e-10):
        # This intentionally follows scoringutils, whose message says 10 digits
        # but whose implementation rounds to 9.
        warnings.warn(
            "The quantile_level column appears to have a rounding issue; "
            "rounding quantile levels to 9 decimal places.",
            MetricScoringWarning,
            stacklevel=3,
        )
        forecast["quantile_level"] = forecast["quantile_level"].round(9)

    duplicate_key = [*FORECAST_UNIT_COLUMNS, "quantile_level"]
    duplicated = forecast.duplicated(duplicate_key, keep=False)
    if duplicated.any():
        raise ForecastValidationError(
            "Each forecast unit must contain at most one prediction for each "
            "quantile level; duplicate combinations were found."
        )

    had_missing_rows = bool(missing_rows.any())
    forecast = forecast.loc[~missing_rows]
    if forecast.empty:
        raise ForecastValidationError(
            "No scoreable forecasts remain after rows with missing values "
            "were removed."
        )
    if had_missing_rows:
        logger.info(
            "Some rows containing NA values were removed. "
            "This is fine if not unexpected."
        )

    return forecast


def _grid_key(values: pd.Series) -> tuple[float, ...]:
    return tuple(np.sort(values.to_numpy(dtype=np.float64, copy=False)))


def _symmetric_pairs(
    quantiles: np.ndarray,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Return lower/upper column indexes, or None for an incomplete interval."""
    nonmedian = np.flatnonzero(quantiles != 0.5)
    ranges = np.round(np.abs(2 * quantiles[nonmedian] - 1) * 100, 10)
    if any(
        np.count_nonzero(ranges == interval_range) != 2
        for interval_range in np.unique(ranges)
    ):
        return None

    # quantile_to_interval_numeric() orders intervals by increasing range.
    lower = np.flatnonzero(quantiles < 0.5)[::-1]
    upper = np.empty(lower.size, dtype=np.intp)
    for index, lower_index in enumerate(lower):
        matching = np.flatnonzero(
            np.round(np.abs(2 * quantiles - 1) * 100, 10)
            == np.round((1 - 2 * quantiles[lower_index]) * 100, 10)
        )
        matching = matching[quantiles[matching] > 0.5]
        if matching.size != 1:
            return None
        upper[index] = matching[0]
    return lower, upper


def _wis_components(
    observed: np.ndarray,
    predicted: np.ndarray,
    quantiles: np.ndarray,
) -> dict[str, np.ndarray] | None:
    pairs = _symmetric_pairs(quantiles)
    if pairs is None:
        return None
    lower_indexes, upper_indexes = pairs
    lower = predicted[:, lower_indexes]
    upper = predicted[:, upper_indexes]

    # interval_score() rejects a complete metric batch if any bound is crossed.
    if np.any(upper < lower):
        return None

    y = observed[:, np.newaxis]
    alpha = 2 * quantiles[lower_indexes]
    dispersion_parts = (upper - lower) * alpha / 2
    # Preserve scoringutils' operation order, including its NaN result for the
    # zero-width probability tail at quantile levels 0 and 1.
    with np.errstate(divide="ignore", invalid="ignore"):
        overprediction_parts = (
            2 / alpha * (lower - y) * (y < lower).astype(float) * alpha / 2
        )
        underprediction_parts = (
            2 / alpha * (y - upper) * (y > upper).astype(float) * alpha / 2
        )

    has_median = np.any(quantiles == 0.5)
    denominator = lower_indexes.size + (0.5 if has_median else 0.0)
    if denominator == 0:
        return None

    if has_median:
        median = predicted[:, quantiles == 0.5][:, 0]
        median_overprediction = np.where(observed < median, median - observed, 0.0)
        median_underprediction = np.where(observed > median, observed - median, 0.0)
        dispersion_parts = np.column_stack(
            (np.zeros(observed.size), dispersion_parts)
        )
        overprediction_parts = np.column_stack(
            (0.5 * median_overprediction, overprediction_parts)
        )
        underprediction_parts = np.column_stack(
            (0.5 * median_underprediction, underprediction_parts)
        )

    dispersion = dispersion_parts.sum(axis=1) / denominator
    overprediction = overprediction_parts.sum(axis=1) / denominator
    underprediction = underprediction_parts.sum(axis=1) / denominator
    wis_parts = dispersion_parts + overprediction_parts + underprediction_parts
    return {
        "wis": wis_parts.sum(axis=1) / denominator,
        "overprediction": overprediction,
        "underprediction": underprediction,
        "dispersion": dispersion,
    }


def _bias(
    observed: np.ndarray,
    predicted: np.ndarray,
    quantiles: np.ndarray,
) -> np.ndarray | None:
    if not np.any(quantiles <= 0.5) or not np.any(quantiles >= 0.5):
        return None
    if np.any(np.diff(predicted, axis=1) < 0):
        return None

    median_mask = quantiles == 0.5
    if median_mask.any():
        median = predicted[:, median_mask][:, 0]
    else:
        lower_index = np.flatnonzero(quantiles < 0.5)[-1]
        upper_index = np.flatnonzero(quantiles > 0.5)[0]
        weight = (0.5 - quantiles[lower_index]) / (
            quantiles[upper_index] - quantiles[lower_index]
        )
        median = predicted[:, lower_index] + weight * (
            predicted[:, upper_index] - predicted[:, lower_index]
        )

    result = np.empty(observed.size, dtype=np.float64)
    at_median = observed == median
    below = observed < median
    above = observed > median
    result[at_median] = 0.0

    below_minimum = below & (observed < predicted[:, 0])
    result[below_minimum] = 1.0
    inside_below = below & ~below_minimum
    if inside_below.any():
        eligible = predicted[inside_below] <= observed[inside_below, np.newaxis]
        q = np.where(eligible, quantiles, -np.inf).max(axis=1)
        result[inside_below] = 1 - 2 * q

    above_maximum = above & (observed > predicted[:, -1])
    result[above_maximum] = -1.0
    inside_above = above & ~above_maximum
    if inside_above.any():
        eligible = predicted[inside_above] >= observed[inside_above, np.newaxis]
        q = np.where(eligible, quantiles, np.inf).min(axis=1)
        result[inside_above] = 1 - 2 * q
    return result


def _coverage(
    observed: np.ndarray,
    predicted: np.ndarray,
    quantiles: np.ndarray,
    interval_range: float,
) -> np.ndarray | None:
    lower_q = (100 - interval_range) / 200
    upper_q = 1 - lower_q
    lower_indexes = np.flatnonzero(quantiles == lower_q)
    upper_indexes = np.flatnonzero(quantiles == upper_q)
    if lower_indexes.size != 1 or upper_indexes.size != 1:
        return None
    lower = predicted[:, lower_indexes[0]]
    upper = predicted[:, upper_indexes[0]]
    return (observed >= lower) & (observed <= upper)


def _warn_metric_failure(metric_name: str, message: str) -> None:
    """Report one failed metric without aborting the remaining metrics."""
    warnings.warn(
        f"Metric `{metric_name}` could not be calculated: {message}.",
        MetricScoringWarning,
        stacklevel=3,
    )


def _wis_failure_message(
    predicted: np.ndarray, quantiles: np.ndarray
) -> str:
    if _symmetric_pairs(quantiles) is None:
        return (
            "the quantile levels do not provide matching lower and upper "
            "bounds for every interval"
        )
    if np.any(
        predicted[:, quantiles > 0.5]
        < predicted[:, quantiles < 0.5][:, ::-1]
    ):
        return (
            "at least one prediction interval has a lower bound greater "
            "than its upper bound"
        )
    return "no valid forecast intervals were available"


def _bias_failure_message(
    predicted: np.ndarray, quantiles: np.ndarray
) -> str:
    if not np.any(quantiles <= 0.5):
        return "at least one quantile at or below 0.5 is required"
    if not np.any(quantiles >= 0.5):
        return "at least one quantile at or above 0.5 is required"
    if np.any(np.diff(predicted, axis=1) < 0):
        return "predictions must be nondecreasing as quantile levels increase"
    return "bias could not be computed"


def _score_arrays(
    units: pd.DataFrame,
    observed: np.ndarray,
    predicted: np.ndarray,
    quantiles: Sequence[float],
) -> pd.DataFrame:
    quantile_array = np.asarray(quantiles, dtype=np.float64)
    result = units.reset_index(drop=True).copy()
    components = _wis_components(observed, predicted, quantile_array)
    if components is not None:
        for name, values in components.items():
            result[name] = values
    else:
        message = _wis_failure_message(predicted, quantile_array)
        for name in ("wis", "overprediction", "underprediction", "dispersion"):
            _warn_metric_failure(name, message)

    bias = _bias(observed, predicted, quantile_array)
    if bias is not None:
        result["bias"] = bias
    else:
        _warn_metric_failure(
            "bias", _bias_failure_message(predicted, quantile_array)
        )

    for interval_range in (50, 95):
        coverage = _coverage(observed, predicted, quantile_array, interval_range)
        if coverage is not None:
            result[f"interval_coverage_{interval_range}"] = coverage
        else:
            lower_q = (100 - interval_range) / 200
            upper_q = 1 - lower_q
            _warn_metric_failure(
                f"interval_coverage_{interval_range}",
                f"{interval_range}% coverage requires the {lower_q:g} and "
                f"{upper_q:g} quantiles",
            )

    median_indexes = np.flatnonzero(quantile_array == 0.5)
    if median_indexes.size == 1:
        result["ae_median"] = np.abs(observed - predicted[:, median_indexes[0]])
    else:
        _warn_metric_failure(
            "ae_median", "absolute median error requires the 0.5 quantile"
        )
    return result


def _score_grid(group: pd.DataFrame, quantiles: Sequence[float]) -> pd.DataFrame:
    """Score a batch sharing one grid (fallback for heterogeneous input)."""
    unit_rows: list[dict[str, object]] = []
    prediction_rows: list[np.ndarray] = []
    observed_values: list[float] = []
    grouped = group.groupby(FORECAST_UNIT_COLUMNS, sort=False, observed=True)
    for unit_key, unit_group in grouped:
        ordered = unit_group.sort_values("quantile_level", kind="stable")
        predictions = ordered["predicted"].to_numpy(dtype=np.float64)
        if not isinstance(unit_key, tuple):
            unit_key = (unit_key,)
        unit = dict(zip(FORECAST_UNIT_COLUMNS, unit_key, strict=True))

        # score.forecast_quantile() uses observed = unique(observed) while
        # transposing. data.table recycles the prediction vector when a unit
        # contains multiple observed values, yielding one score row per value.
        for observed in pd.unique(unit_group["observed"]):
            unit_rows.append(unit)
            prediction_rows.append(predictions)
            observed_values.append(float(observed))

    units = pd.DataFrame(unit_rows, columns=FORECAST_UNIT_COLUMNS)
    predicted = np.vstack(prediction_rows)
    observed = np.asarray(observed_values, dtype=np.float64)
    return _score_arrays(units, observed, predicted, quantiles)


def _score_uniform_grid(
    forecast: pd.DataFrame,
    unit_codes: np.ndarray,
    group_size: int,
) -> pd.DataFrame | None:
    """Vectorized fast path when every forecast unit uses the same grid."""
    unit_count = int(unit_codes.max()) + 1
    quantile_values = forecast["quantile_level"].to_numpy(dtype=np.float64, copy=False)
    row_order = np.lexsort((quantile_values, unit_codes))
    quantile_matrix = quantile_values[row_order].reshape(unit_count, group_size)
    if not np.all(quantile_matrix == quantile_matrix[0]):
        return None

    first_rows = np.full(unit_count, len(forecast), dtype=np.intp)
    np.minimum.at(first_rows, unit_codes, np.arange(len(forecast)))
    all_observed = forecast["observed"].to_numpy(dtype=np.float64, copy=False)
    if not np.all(all_observed == all_observed[first_rows][unit_codes]):
        return None
    units = forecast.iloc[first_rows][FORECAST_UNIT_COLUMNS]
    observed = all_observed[first_rows]
    predicted = forecast["predicted"].to_numpy(dtype=np.float64, copy=False)[
        row_order
    ].reshape(unit_count, group_size)
    return _score_arrays(units, observed, predicted, quantile_matrix[0])


def score_quantile_forecasts(data: pd.DataFrame) -> pd.DataFrame:
    """Return the same unsummarized scores as EpiBench's scoringutils call.

    The implementation batches forecast units that share a quantile grid and
    uses NumPy arrays for every metric, avoiding per-row Python and subprocess
    overhead.
    """
    forecast = _prepare_forecasts(data)
    unit_index = pd.MultiIndex.from_frame(forecast[FORECAST_UNIT_COLUMNS])
    unit_codes, _ = pd.factorize(unit_index, sort=False)
    counts = np.bincount(unit_codes)
    unique_counts = pd.unique(counts)
    if unique_counts.size > 1:
        count_text = ", ".join(str(value) for value in unique_counts)
        warnings.warn(
            "Forecast units contain different numbers of quantiles "
            f"({count_text}). Scores can still be calculated, but comparisons "
            "between units may be less meaningful.",
            MetricScoringWarning,
            stacklevel=2,
        )

    if counts.size and np.all(counts == counts[0]):
        output = _score_uniform_grid(forecast, unit_codes, int(counts[0]))
        if output is not None:
            return output

    # scoringutils supports different quantile grids in one input. EpiBench's
    # normal validation disallows that, but retain the behavior as a fallback.
    unit_groups = forecast.groupby(FORECAST_UNIT_COLUMNS, sort=False, observed=True)
    grid_keys = np.empty(len(forecast), dtype=object)
    for row_indexes in unit_groups.indices.values():
        key = _grid_key(forecast.iloc[row_indexes]["quantile_level"])
        grid_keys[row_indexes] = [key] * len(row_indexes)
    forecast["_scoringutils_grid"] = grid_keys

    scored = []
    for quantile_grid, group in forecast.groupby(
        "_scoringutils_grid", sort=True, observed=True
    ):
        scored.append(_score_grid(group, quantile_grid))

    output = pd.concat(scored, ignore_index=True, sort=False)
    return output
