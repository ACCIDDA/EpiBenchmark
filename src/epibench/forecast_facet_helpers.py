"""Forecast-facet normalization and comparison helpers."""

from __future__ import annotations

import pandas as pd

FACET_COLUMNS = [
    "reference_date",
    "target_end_date",
    "location",
    "horizon",
    "quantile_level",
]


def _normalize_facet_rows(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize facet columns without rejecting removable extra quantiles."""
    missing_columns = set(FACET_COLUMNS) - set(data.columns)
    if missing_columns:
        raise ValueError(
            "Forecast data is missing facet columns: "
            f"{sorted(missing_columns)}"
        )

    normalized = data[FACET_COLUMNS].copy()
    for date_column in ("reference_date", "target_end_date"):
        normalized[date_column] = pd.to_datetime(
            normalized[date_column], errors="raise"
        ).dt.strftime("%Y-%m-%d")
    for string_column in ("location", "horizon"):
        normalized[string_column] = normalized[string_column].astype(str)
    raw_quantiles = (
        normalized["quantile_level"]
        .astype("string")
        .fillna("<missing>")
        .astype(object)
    )
    numeric_quantiles = pd.to_numeric(raw_quantiles, errors="coerce")
    numeric_mask = numeric_quantiles.notna()
    raw_quantiles.loc[numeric_mask] = (
        numeric_quantiles.loc[numeric_mask]
        .round(10)
        .map(lambda value: f"{value:g}")
    )
    normalized["quantile_level"] = raw_quantiles.astype(str)
    return normalized


def facet_keys(data: pd.DataFrame) -> set[tuple[str, ...]]:
    """Return normalized facet keys used for model comparisons."""
    normalized = _normalize_facet_rows(data)
    return {
        tuple(row)
        for row in normalized.drop_duplicates().itertuples(index=False, name=None)
    }


def submitted_facet_union(
    submitted_model_dict: dict[str, pd.DataFrame],
) -> set[tuple[str, ...]]:
    """Find facets present in any user-submitted model."""
    facet_sets = [
        facet_keys(forecast_df)
        for forecast_df in submitted_model_dict.values()
    ]
    if not facet_sets:
        return set()
    return set.union(*facet_sets)


def pare_down_extra_models(
    submitted_model_dict: dict[str, pd.DataFrame],
    extra_model_dict: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], list[dict[str, object]]]:
    """Restrict included hub models to facets present in submitted models."""
    allowed_facets = submitted_facet_union(submitted_model_dict)
    pared_model_dict = {}
    facet_paring_summaries = []

    for model_name, forecast_df in extra_model_dict.items():
        model_facet_keys = facet_keys(forecast_df)
        normalized_rows = _normalize_facet_rows(forecast_df)
        keep_mask = pd.Series(
            [
                tuple(row) in allowed_facets
                for row in normalized_rows.itertuples(index=False, name=None)
            ],
            index=forecast_df.index,
        )
        pared_model_dict[model_name] = forecast_df.loc[keep_mask].copy()

        retained_facets = model_facet_keys & allowed_facets
        facet_paring_summaries.append(
            {
                "model_name": model_name,
                "original_facets": len(model_facet_keys),
                "retained_facets": len(retained_facets),
                "removed_facets": len(model_facet_keys - allowed_facets),
            }
        )

    return pared_model_dict, facet_paring_summaries
