"""Fast Python implementation of the quantile scoringutils metrics EpiBench uses.

The formulas and grouping behavior in this module mirror scoringutils 2.2.0.9000
for the metric list historically configured in :mod:`epibench.scoring_bridge`.
They are deliberately kept private to EpiBench rather than presented as a
general Python port of scoringutils.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

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
    missing = [
        column
        for column in [*FORECAST_UNIT_COLUMNS, *REQUIRED_COLUMNS]
        if column not in data.columns
    ]
    if missing:
        raise ValueError(f"Forecast data is missing required columns: {missing}")


def _prepare_forecasts(data: pd.DataFrame) -> pd.DataFrame:
    """Match as_forecast_quantile(), set_forecast_unit(), and clean_forecast()."""
    _check_columns(data)
    columns = [*REQUIRED_COLUMNS, *FORECAST_UNIT_COLUMNS]
    forecast = data.loc[:, columns].copy()

    for column in REQUIRED_COLUMNS:
        if pd.api.types.is_bool_dtype(forecast[column]):
            raise ValueError(f"Forecast column '{column}' must be numeric.")
        try:
            forecast[column] = pd.to_numeric(forecast[column], errors="raise")
        except (TypeError, ValueError) as error:
            raise ValueError(f"Forecast column '{column}' must be numeric.") from error

    forecast = forecast.drop_duplicates()

    quantiles = forecast["quantile_level"].to_numpy(dtype=np.float64, copy=False)
    finite_quantiles = quantiles[~np.isnan(quantiles)]
    if np.any((finite_quantiles < 0) | (finite_quantiles > 1)):
        raise ValueError("Quantile levels must be between 0 and 1 inclusive.")

    unique_quantiles = np.unique(finite_quantiles)
    if unique_quantiles.size > 1 and np.any(np.diff(unique_quantiles) <= 1e-10):
        # This intentionally follows scoringutils, whose message says 10 digits
        # but whose implementation rounds to 9.
        forecast["quantile_level"] = forecast["quantile_level"].round(9)

    duplicate_key = [*FORECAST_UNIT_COLUMNS, "quantile_level"]
    duplicated = forecast.duplicated(duplicate_key, keep=False)
    if duplicated.any():
        raise ValueError(
            "There are instances with more than one forecast for the same "
            "forecast unit and quantile level."
        )

    forecast = forecast.dropna(axis=0, how="any")
    if forecast.empty:
        raise ValueError(
            "After removing rows with NA values in the data, no forecasts are left."
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

    bias = _bias(observed, predicted, quantile_array)
    if bias is not None:
        result["bias"] = bias

    for interval_range in (50, 95):
        coverage = _coverage(observed, predicted, quantile_array, interval_range)
        if coverage is not None:
            result[f"interval_coverage_{interval_range}"] = coverage

    median_indexes = np.flatnonzero(quantile_array == 0.5)
    if median_indexes.size == 1:
        result["ae_median"] = np.abs(observed - predicted[:, median_indexes[0]])
    return result


def _score_grid(group: pd.DataFrame, quantiles: Sequence[float]) -> pd.DataFrame:
    """Score a batch sharing one grid (fallback for heterogeneous input)."""
    ordered = group.sort_values("quantile_level", kind="stable")
    grouped = ordered.groupby(FORECAST_UNIT_COLUMNS, sort=False, observed=True)
    units = grouped[FORECAST_UNIT_COLUMNS].first().reset_index(drop=True)
    predicted = np.vstack(grouped["predicted"].agg(list).to_numpy()).astype(np.float64)
    observed = grouped["observed"].first().to_numpy(dtype=np.float64)
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
    units = forecast.iloc[first_rows][FORECAST_UNIT_COLUMNS]
    observed = forecast["observed"].to_numpy(dtype=np.float64, copy=False)[
        first_rows
    ]
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
