"""Bridge between the Python package and R scoringutils functionality."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

FACET_COLUMNS = [
    "reference_date",
    "target_end_date",
    "location",
    "horizon",
    "quantile_level",
]

R_SCORING_SCRIPT = """#!/usr/bin/env Rscript
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2) {
  stop("Usage: Rscript score_with_scoringutils.R <input_csv> <output_csv>")
}

input_csv <- args[1]
output_csv <- args[2]

suppressPackageStartupMessages(library(scoringutils))
suppressPackageStartupMessages(library(purrr))

df <- read.csv(input_csv, stringsAsFactors = FALSE)
df$target_end_date <- as.Date(df$target_end_date)

forecast_object <- as_forecast_quantile(
  df,
  forecast_unit = c("model", "reference_date", "target_end_date", "location", "horizon"),
  observed = "observed",
  predicted = "predicted",
  quantile = "quantile_level"
)

metrics <- list(
  wis = wis,
  overprediction = overprediction_quantile,
  underprediction = underprediction_quantile,
  dispersion = dispersion_quantile,
  bias = bias_quantile,
  interval_coverage_50 = interval_coverage,
  interval_coverage_95 = partial(interval_coverage, interval_range = 95),
  ae_median = ae_median_quantile
)

scores <- score(forecast_object, metrics = metrics)
write.csv(scores, output_csv, row.names = FALSE)
"""

R_SCRIPT_NOT_FOUND_ERROR = """\
Could not find Rscript on your PATH.

To run 'epibench score' command, users need:

  • An R installation
  • Rscript available on your PATH
  • The CRAN packages 'scoringutils' and 'purrr'

On HPC systems, users may need to load an R module first:

    module avail R
    module load R/<version>

Then verify:

    Rscript --version
    Rscript -e "library(scoringutils); library(purrr)"
"""


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
    """Run scoringutils via an external Rscript process."""

    def __init__(self, baseline_model: str, rscript_executable: str | None = None):
        self.baseline_model = baseline_model
        self.rscript_executable = rscript_executable or shutil.which("Rscript")
        if not self.rscript_executable:
            raise RuntimeError(R_SCRIPT_NOT_FOUND_ERROR)


    # score with R scoringutils
    def score_forecasts(self, data: pd.DataFrame) -> pd.DataFrame:
        """Score forecast data using scoringutils in a subprocess."""
        payload = data.copy()
        unit_cols = ["target_end_date", "location", "horizon", "model"]
        for col in unit_cols:
            if col in payload.columns:
                payload[col] = payload[col].astype(str)

        with tempfile.TemporaryDirectory(prefix="epibench-score-") as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / "input.csv"
            output_path = tmp_path / "scores.csv"
            script_path = tmp_path / "score_with_scoringutils.R"

            payload.to_csv(input_path, index=False)
            script_path.write_text(R_SCORING_SCRIPT, encoding="utf-8")

            command = [
                self.rscript_executable,
                str(script_path),
                str(input_path),
                str(output_path),
            ]

            logger.info("Running scoringutils via Rscript...")
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                stderr = result.stderr.strip()
                stdout = result.stdout.strip()
                details = "\n".join(part for part in [stdout, stderr] if part)
                normalized_details = details.replace("‘", "'").replace("’", "'").lower()
                if "there is no package called" in normalized_details:
                    if "scoringutils" in normalized_details:
                        raise RuntimeError(
                            "R scoring process failed because the R package `scoringutils` is not installed.\n"
                            "Install it in R with:\n"
                            "Rscript -e 'install.packages(c(\"scoringutils\", \"purrr\"))'"
                        )
                    if "purrr" in normalized_details:
                        raise RuntimeError(
                            "R scoring process failed because the R package `purrr` is not installed.\n"
                            "Install it in R with:\n"
                            "Rscript -e 'install.packages(c(\"scoringutils\", \"purrr\"))'"
                        )
                raise RuntimeError(
                    "R scoring process failed."
                    + (f"\n{details}" if details else "")
                )

            if not output_path.exists():
                raise RuntimeError("R scoring process completed without producing an output file.")

            # add rwis as a column by comparing each entry with the baseline model
            output = pd.read_csv(output_path)
            baseline_scores = output[output['model'] == self.baseline_model]
            if baseline_scores.empty:
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
                output = output.merge(baseline_wis, on=join_cols, how="left")
                output["rwis"] = output["wis"].div(output["baseline_wis"]).where(
                    output["baseline_wis"].notna() & output["baseline_wis"].ne(0)
                )
                output = output.drop(columns=["baseline_wis"])

            # return output
            logger.info("Success ✅")
            return output
