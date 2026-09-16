"""Scoring entry point and forecast-facet helpers."""

from __future__ import annotations

import logging
import pandas as pd

from .scoringutils_python import SCORE_COLUMNS, score_quantile_forecasts

logger = logging.getLogger(__name__)

FACET_COLUMNS = [
    "reference_date",
    "target_end_date",
    "location",
    "horizon",
    "quantile_level",
]
OUTPUT_COLUMNS = [
    "model",
    "reference_date",
    "target_end_date",
    "location",
    "horizon",
    *SCORE_COLUMNS,
    "rwis",
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
    """Restrict included hub models to facets present in any submitted model."""
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
        removed_count = len(model_facet_keys - allowed_facets)
        facet_paring_summaries.append(
            {
                "model_name": model_name,
                "original_facets": len(model_facet_keys),
                "retained_facets": len(retained_facets),
                "removed_facets": removed_count,
            }
        )

    return pared_model_dict, facet_paring_summaries


class ScoringBridge:
    """Score forecasts with the in-process Python scoringutils equivalent."""

    def __init__(self, baseline_model: str, rscript_executable: str | None = None):
        self.baseline_model = baseline_model
        # Retain the old keyword so external callers do not break. It is no
        # longer used now that scoring runs in-process.
        self.rscript_executable = rscript_executable

    def score_forecasts(self, data: pd.DataFrame) -> pd.DataFrame:
        """Score forecast data and add WIS relative to the baseline model."""
        payload = data.copy()
        unit_cols = [
            "reference_date",
            "target_end_date",
            "location",
            "horizon",
            "model",
        ]
        for col in unit_cols:
            if col in payload.columns:
                payload[col] = payload[col].astype(str)
        if "target_end_date" in payload:
            payload["target_end_date"] = pd.to_datetime(
                payload["target_end_date"], errors="raise"
            ).dt.strftime("%Y-%m-%d")
        # read.csv() inferred numeric forecast-unit columns in the old bridge.
        # Preserve that observable behavior without doing a CSV round trip.
        for col in ("model", "location", "horizon"):
            if col in payload:
                numeric = pd.to_numeric(payload[col], errors="coerce")
                if numeric.notna().all():
                    payload[col] = numeric

        logger.info("Scoring quantile forecasts in Python...")
        output = score_quantile_forecasts(payload)
        baseline_scores = output[output["model"] == self.baseline_model]
        if baseline_scores.empty or "wis" not in output:
            output["rwis"] = pd.NA
        else:
            join_cols = [
                "reference_date",
                "target_end_date",
                "location",
                "horizon",
            ]
            baseline_wis = baseline_scores[join_cols + ["wis"]].rename(
                columns={"wis": "baseline_wis"}
            )
            output = output.merge(baseline_wis, on=join_cols, how="left", sort=False)
            output["rwis"] = output["wis"].div(output["baseline_wis"]).where(
                output["baseline_wis"].notna() & output["baseline_wis"].ne(0)
            )
            output = output.drop(columns=["baseline_wis"])

        # A scoringutils metric failure normally omits that metric column. The
        # EpiBenchmark file contract is stricter: always emit the full schema.
        for column in OUTPUT_COLUMNS:
            if column not in output:
                output[column] = pd.NA
        output = output.loc[:, OUTPUT_COLUMNS]

        logger.info("Success ✅")
        return output
