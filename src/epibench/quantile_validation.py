"""Validation helpers for forecast quantile inputs used in scoring."""

import pandas as pd

FORECAST_UNIT_COLUMNS = [
    "model",
    "reference_date",
    "target_end_date",
    "location",
    "horizon",
]
QUANTILE_ROUNDING_DIGITS = 10


def validate_for_scoring_library_challenge_quantiles(model_dict: dict[str, pd.DataFrame]) -> None:
    """write"""
    pass # TODO 


def validate_for_scoring_config_quantiles(model_dict: dict[str, pd.DataFrame]) -> None:
    """
    Validate quantile data from user-supplied model data (specified via config).

    (By the time the dfs reach this function, they are already in scoringutils format,
    so the quantile value column is 'quantile_level')

    Fatal failure if:
        - quantiles outside of [0, 1] are found
        - non-numeric quantiles are found
        - a median quantile is not present (0.5)
        - a forecast unit repeats a quantile more than once
        - the number of quantiles is unbalanced for a forecat unit
        - a forecast unit has asymmetrical quantiles
        - different quantile units are used across models
        - different quantile units are used within a model
    """

    expected_quantile_grid: tuple[float, ...] | None = None
    expected_grid_model: str | None = None

    # iterate over every model in the model_dict
    for model_name, forecast_df in model_dict.items():
        normalized = forecast_df.copy()
        normalized["quantile_level_raw"] = normalized["quantile_level"]
        normalized["quantile_level"] = pd.to_numeric(
            normalized["quantile_level"], errors="coerce"
        )

        # fail if any quantile level is non-numeric or outside [0, 1]
        invalid_quantiles = normalized[
            normalized["quantile_level"].isna()
            | ~normalized["quantile_level"].between(0, 1, inclusive="both")
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

        # round all quantiles to 10 digits (likely unnecessary but safe)
        normalized["quantile_level"] = normalized["quantile_level"].round(
            QUANTILE_ROUNDING_DIGITS
        )

        # build forecast units (unique combinations of model, target_end_date, location, horizon)
        model_quantile_grid: tuple[float, ...] | None = None
        for _, group in normalized.groupby(FORECAST_UNIT_COLUMNS, sort=False):
            group = group.sort_values("quantile_level") # using scoringutil column naming
            forecast_unit_row = group.iloc[0]
            forecast_unit = ", ".join(
                f"{column}={forecast_unit_row[column]}"
                for column in FORECAST_UNIT_COLUMNS
            )
            quantile_levels = tuple(group["quantile_level"].tolist())
            unique_quantile_levels = tuple(sorted(set(quantile_levels)))
            quantile_grid_text = ", ".join(
                f"{quantile_level:g}" for quantile_level in unique_quantile_levels
            )

            # fail if a forecast unit repeats the same quantile level more than once.
            if len(quantile_levels) != len(unique_quantile_levels):
                raise ValueError(
                    f"Model '{model_name}' contains duplicate quantile levels for "
                    f"forecast unit {forecast_unit}. Found quantile grid "
                    f"[{', '.join(f'{quantile_level:g}' for quantile_level in quantile_levels)}]."
                )

            # fail if a forecast unit does not include the median quantile.
            if 0.5 not in unique_quantile_levels:
                raise ValueError(
                    f"Model '{model_name}' is missing the median quantile (0.5) "
                    f"for forecast unit {forecast_unit}. Config-route scoring "
                    "requires a symmetric quantile grid that includes 0.5."
                )

            # fail if the number of lower and upper quantiles is unbalanced
            lower_quantiles = [
                quantile for quantile in unique_quantile_levels if quantile < 0.5
            ]
            upper_quantiles = [
                quantile for quantile in unique_quantile_levels if quantile > 0.5
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
                    f"[{', '.join(f'{quantile_level:g}' for quantile_level in model_quantile_grid)}] "
                    f"but found [{quantile_grid_text}] for forecast unit "
                    f"{forecast_unit}."
                )
            
        # fail if different models are using different quantile sets 
        if expected_quantile_grid is None:
            expected_quantile_grid = model_quantile_grid
            expected_grid_model = model_name
            continue
        if model_quantile_grid != expected_quantile_grid:
            raise ValueError(
                "Config-route scoring requires all scored models to use the same "
                "quantile grid. "
                f"Model '{model_name}' uses "
                f"[{', '.join(f'{quantile_level:g}' for quantile_level in model_quantile_grid)}], "
                f"but model '{expected_grid_model}' uses "
                f"[{', '.join(f'{quantile_level:g}' for quantile_level in expected_quantile_grid)}]."
            )
