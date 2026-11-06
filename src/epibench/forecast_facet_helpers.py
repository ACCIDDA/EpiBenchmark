"""Forecast-facet normalization and comparison helpers."""

from __future__ import annotations

import polars as pl

from .dataframes import to_polars, normalize_dates

FACET_COLUMNS = [
    "reference_date",
    "target_end_date",
    "location",
    "horizon",
    "quantile_level",
]


def _normalize_facet_rows(data: pl.DataFrame) -> pl.DataFrame:
    """Normalize facet columns without rejecting removable extra quantiles."""
    missing_columns = set(FACET_COLUMNS) - set(data.columns)
    if missing_columns:
        raise ValueError(
            "Forecast data is missing facet columns: " f"{sorted(missing_columns)}"
        )

    normalized = normalize_dates(
        to_polars(data).select(FACET_COLUMNS),
        ["reference_date", "target_end_date"],
        strings=True,
    )
    normalized = normalized.with_columns(pl.col("location", "horizon").cast(pl.String))
    raw = normalized["quantile_level"].cast(pl.String).fill_null("<missing>")
    unique_raw = raw.unique(maintain_order=True)
    numeric = unique_raw.cast(pl.Float64, strict=False).fill_nan(None).round(10)
    # Format each distinct quantile once with :g for facet comparison.
    quantiles = {
        text: f"{number:g}" if number is not None else text
        for text, number in zip(unique_raw, numeric)
    }
    return normalized.with_columns(
        raw.replace_strict(quantiles).alias("quantile_level")
    )


def facet_keys(data: pl.DataFrame) -> set[tuple[str, ...]]:
    """Return normalized facet keys used for model comparisons."""
    normalized = _normalize_facet_rows(data)
    return {tuple(row) for row in normalized.unique(maintain_order=True).iter_rows()}


def submitted_facet_union(
    submitted_model_dict: dict[str, pl.DataFrame],
) -> set[tuple[str, ...]]:
    """Find facets present in any user-submitted model."""
    facet_sets = [
        facet_keys(forecast_df) for forecast_df in submitted_model_dict.values()
    ]
    if not facet_sets:
        return set()
    return set.union(*facet_sets)


def pare_down_extra_models(
    submitted_model_dict: dict[str, pl.DataFrame],
    extra_model_dict: dict[str, pl.DataFrame],
) -> tuple[dict[str, pl.DataFrame], list[dict[str, object]]]:
    """Restrict included hub models to facets present in submitted models."""
    allowed_facets = submitted_facet_union(submitted_model_dict)
    pared_model_dict = {}
    facet_paring_summaries = []

    for model_name, forecast_df in extra_model_dict.items():
        model_facet_keys = facet_keys(forecast_df)
        normalized_rows = _normalize_facet_rows(forecast_df)
        allowed = pl.DataFrame(
            sorted(allowed_facets),
            schema={c: pl.String for c in FACET_COLUMNS},
            orient="row",
        )
        row_indexes = normalized_rows.with_row_index("_facet_row").join(
            allowed,
            on=FACET_COLUMNS,
            how="semi",
            maintain_order="left",
            nulls_equal=True,
        )["_facet_row"]
        pared_model_dict[model_name] = to_polars(forecast_df)[row_indexes]

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
