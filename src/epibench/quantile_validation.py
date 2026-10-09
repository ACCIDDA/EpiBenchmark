"""Validation helpers for forecast quantile inputs used in scoring."""

import logging
from typing import Dict, Iterable, List, Optional, Set, Tuple

import pandas as pd

from .scoring_summary import record_filtered_facets

# 1 forecast unit = 1 unique combination of model, target_end_date, reference_date, location, horizon 
FORECAST_UNIT_COLUMNS = [
    "model",
    "reference_date",
    "target_end_date",
    "location",
    "horizon",
]
QUANTILE_ROUNDING_DIGITS = 10
logger = logging.getLogger(__name__)


def _prepare_quantile_columns(forecast_df: pd.DataFrame) -> pd.DataFrame:
    """Preserve exact quantile strings while deriving numeric helpers for validation."""
    normalized = forecast_df.copy()
    normalized["quantile_level"] = normalized["quantile_level"].astype("string")
    normalized["quantile_level_raw"] = normalized["quantile_level"].fillna("<missing>")
    normalized["quantile_level_numeric"] = pd.to_numeric(
        normalized["quantile_level"], errors="coerce"
    )
    return normalized


def _sort_quantile_strings(
    quantile_levels: Iterable[str],
) -> List[str]:
    """Return exact quantile strings in deterministic numeric order."""
    return sorted(
        quantile_levels,
        key=lambda quantile_level: (float(quantile_level), str(quantile_level)),
    )


def _format_quantile_grid(quantile_levels: Iterable[str]) -> str:
    """Render a quantile grid using the exact submitted string values."""
    return ", ".join(str(quantile_level) for quantile_level in quantile_levels)


def _finalize_quantile_column(normalized: pd.DataFrame) -> pd.DataFrame:
    """Drop validation helpers and restore numeric quantiles for downstream scoring."""
    finalized = normalized.copy()
    finalized["quantile_level"] = finalized["quantile_level_numeric"].round(
        QUANTILE_ROUNDING_DIGITS
    )
    return finalized.drop(
        columns=["quantile_level_raw", "quantile_level_numeric"],
        errors="ignore",
    )


def validate_for_scoring_library_challenge_quantiles(
    model_dict: Dict[str, pd.DataFrame],
    quantiles: List[str],
    filtered_facets_by_file: Optional[Dict[str, Set[str]]] = None,
) -> None:
    """
    Validate quantile data for challenge-library scoring.

    For library challenges, forecast units must include all quantiles required by the
    challenge definition. Additional quantiles are allowed, but they are removed
    before scoring and reported to the user via a logger message.

    Fails if:
        - quantiles outside of [0,1]
        - duplicate quantiles found in one forecast unit
        - any required quantiles are missing for a forecast unit
    
    This function allows extra quantiles to exist, but it filters
    them out and logs this to the user.
    """

    required_quantiles = tuple(
        _sort_quantile_strings(dict.fromkeys(str(quantile) for quantile in quantiles))
    )
    # for each model in model_data (should just be one model)
    for model_name, forecast_df in model_dict.items():
        normalized = _prepare_quantile_columns(forecast_df)

        # fail if any quantile level is non-numeric or outside [0, 1]
        invalid_quantiles = normalized[
            normalized["quantile_level_numeric"].isna()
            | ~normalized["quantile_level_numeric"].between(0, 1, inclusive="both")
        ]
        if not invalid_quantiles.empty:
            first_invalid = invalid_quantiles.iloc[0]
            forecast_unit = ", ".join(
                f"{column}={first_invalid[column]}" for column in FORECAST_UNIT_COLUMNS
            )
            raise ValueError(
                f"Model '{model_name}' contains an invalid quantile level "
                f"'{first_invalid['quantile_level_raw']}' for forecast unit "
                f"{forecast_unit}. Quantile levels must be numeric values "
                "between 0 and 1 inclusive."
            )

        extra_quantiles_found = set()
        files_with_extra_quantiles = set()

        normalized = normalized.sort_values(
                by=["quantile_level_numeric", "quantile_level"],
                kind="stable",
            )
        for _, group in normalized.groupby(FORECAST_UNIT_COLUMNS, sort=False):
            forecast_unit_row = group.iloc[0]
            forecast_unit = ", ".join(
                f"{column}={forecast_unit_row[column]}"
                for column in FORECAST_UNIT_COLUMNS
            )
            quantile_levels = tuple(str(quantile_level) for quantile_level in group["quantile_level"].tolist())
            unique_quantile_levels = tuple(
                _sort_quantile_strings(set(quantile_levels))
            )

            # fail if a forecast unit repeats the same quantile level more than once.
            if len(quantile_levels) != len(unique_quantile_levels):
                raise ValueError(
                    f"Model '{model_name}' contains duplicate quantile levels for "
                    f"forecast unit {forecast_unit}. Found quantile grid "
                    f"[{_format_quantile_grid(quantile_levels)}]."
                )

            # fail if a forecast unit is missing any quantile required by the challenge.
            missing_quantiles = _sort_quantile_strings(
                set(required_quantiles) - set(unique_quantile_levels)
            )
            if missing_quantiles:
                raise ValueError(
                    f"Model '{model_name}' is missing required challenge quantile "
                    f"[{_format_quantile_grid(missing_quantiles)}] "
                    f"First forecast unit found missing this quantile: {forecast_unit}. Required challenge quantiles are "
                    f"[{_format_quantile_grid(required_quantiles)}]. "
                    "Please ensure exact matches; e.g., `0.50` does not validate with `0.5`"
                )

            extra_quantiles = _sort_quantile_strings(
                set(unique_quantile_levels) - set(required_quantiles)
            )
            extra_quantiles_found.update(extra_quantiles)
            if extra_quantiles and "_source_file" in group.columns:
                files_with_extra_quantiles.update(group["_source_file"].dropna().unique())
        if extra_quantiles_found:
            for input_file in sorted(files_with_extra_quantiles):
                record_filtered_facets(
                    filtered_facets_by_file=filtered_facets_by_file,
                    input_file=str(input_file),
                    facets=["quantile"],
                )

        filtered = normalized[normalized["quantile_level"].isin(required_quantiles)].copy()
        model_dict[model_name] = _finalize_quantile_column(filtered)
    logger.info("Success ✅")


def validate_for_scoring_config_quantiles(model_dict: Dict[str, pd.DataFrame]) -> None:
    """
    Validate quantile data from user-supplied model data (specified via config).

    (By the time the dfs reach this function, they are already in scoringutils format,
    so the quantile value column is 'quantile_level')

    Fatal failure if:
        - quantiles outside of [0, 1] are found
        - non-numeric quantiles are found
        - the minimum safe scoring grid is not present (0.025, 0.25, 0.5, 0.75, 0.975)
        - a forecast unit repeats a quantile more than once
        - the number of quantiles is unbalanced for a forecat unit
        - a forecast unit has asymmetrical quantiles
        - different quantile units are used across models
        - different quantile units are used within a model
    """
    minimum_safe_scoring_grid = ("0.025", "0.25", "0.5", "0.75", "0.975")

    expected_quantile_grid = None  # type: Optional[Tuple[str, ...]]
    expected_grid_model = None  # type: Optional[str]

    # iterate over every model in the model_dict
    for model_name, forecast_df in model_dict.items():
        normalized = _prepare_quantile_columns(forecast_df)

        # fail if any quantile level is non-numeric or outside [0, 1]
        invalid_quantiles = normalized[
            normalized["quantile_level_numeric"].isna()
            | ~normalized["quantile_level_numeric"].between(0, 1, inclusive="both")
        ]
        if not invalid_quantiles.empty:
            first_invalid = invalid_quantiles.iloc[0]
            forecast_unit = ", ".join(
                f"{column}={first_invalid[column]}" for column in FORECAST_UNIT_COLUMNS
            )
            raise ValueError(
                f"Model '{model_name}' contains an invalid quantile level "
                f"'{first_invalid['quantile_level_raw']}' for forecast unit "
                f"{forecast_unit}. Quantile levels must be numeric values "
                "between 0 and 1 inclusive."
            )

        # build forecast units (unique combinations of model, target_end_date, location, horizon)
        model_quantile_grid = None  # type: Optional[Tuple[str, ...]]
        normalized = normalized.sort_values(
                by=["quantile_level_numeric", "quantile_level"],
                kind="stable",
            )
        for _, group in normalized.groupby(FORECAST_UNIT_COLUMNS, sort=False):
            forecast_unit_row = group.iloc[0]
            forecast_unit = ", ".join(
                f"{column}={forecast_unit_row[column]}"
                for column in FORECAST_UNIT_COLUMNS
            )
            quantile_levels = tuple(
                str(quantile_level) for quantile_level in group["quantile_level"].tolist()
            )
            unique_quantile_levels = tuple(_sort_quantile_strings(set(quantile_levels)))
            quantile_grid_text = _format_quantile_grid(unique_quantile_levels)
            unique_quantile_levels_numeric = tuple(
                group.drop_duplicates(subset=["quantile_level"])["quantile_level_numeric"].tolist()
            )

            # fail if a forecast unit repeats the same quantile level more than once.
            if len(quantile_levels) != len(unique_quantile_levels):
                raise ValueError(
                    f"Model '{model_name}' contains duplicate quantile levels for "
                    f"forecast unit {forecast_unit}. Found quantile grid "
                    f"[{_format_quantile_grid(quantile_levels)}]."
                )

            # fail if a forecast unit does not include the minimum grid needed for
            # the default scoringutils metrics we compute.
            missing_minimum_safe_quantiles = _sort_quantile_strings(
                set(minimum_safe_scoring_grid) - set(unique_quantile_levels)
            )
            if missing_minimum_safe_quantiles:
                raise ValueError(
                    f"Model '{model_name}' is missing required quantile "
                    f"[{_format_quantile_grid(missing_minimum_safe_quantiles)}] "
                    f"for forecast unit {forecast_unit}. Config-route scoring "
                    "requires at least the minimum safe quantile grid "
                    f"[{_format_quantile_grid(minimum_safe_scoring_grid)}] "
                    "to support the default scoringutils metrics."
                    "Please ensure exact matches; e.g., `0.50` does not validate with `0.5`."
                )

            # fail if the number of lower and upper quantiles is unbalanced
            lower_quantiles = [
                quantile
                for quantile in unique_quantile_levels_numeric
                if quantile < 0.5
            ]
            upper_quantiles = [
                quantile
                for quantile in unique_quantile_levels_numeric
                if quantile > 0.5
            ]
            if len(lower_quantiles) != len(upper_quantiles):
                raise ValueError(
                    f"Model '{model_name}' has a non-symmetric quantile grid for "
                    f"forecast unit {forecast_unit}. Found quantile grid "
                    f"[{quantile_grid_text}]."
                )
            
            # fail if any lower/upper quantile pair is not symmetric around 0.5
            for lower_quantile, upper_quantile in zip(
                lower_quantiles,
                reversed(upper_quantiles),
                strict=True,
            ):
                if round(lower_quantile + upper_quantile, QUANTILE_ROUNDING_DIGITS) != 1:
                    raise ValueError(
                        f"Model '{model_name}' has a non-symmetric quantile grid "
                        f"for forecast unit {forecast_unit}. Quantiles "
                        f"{lower_quantile:g} and {upper_quantile:g} do not form a "
                        "symmetric pair around 0.5."
                    )
                
            # fail if one model uses different quantile sets across forecast units
            if model_quantile_grid is None:
                model_quantile_grid = unique_quantile_levels
                continue
            if unique_quantile_levels != model_quantile_grid:
                raise ValueError(
                    f"Model '{model_name}' uses different quantile grids across "
                    f"forecast units. Expected "
                    f"[{_format_quantile_grid(model_quantile_grid)}] "
                    f"but found [{quantile_grid_text}] for forecast unit "
                    f"{forecast_unit}."
                )
            
        # fail if different models are using different quantile sets 
        if expected_quantile_grid is None:
            expected_quantile_grid = model_quantile_grid
            expected_grid_model = model_name
        elif model_quantile_grid != expected_quantile_grid:
            raise ValueError(
                "Config-route scoring requires all scored models to use the same "
                "quantile grid. "
                f"Model '{model_name}' uses "
                f"[{_format_quantile_grid(model_quantile_grid)}], "
                f"but model '{expected_grid_model}' uses "
                f"[{_format_quantile_grid(expected_quantile_grid)}]."
            )

        model_dict[model_name] = _finalize_quantile_column(normalized)

    logger.info("Success ✅")
