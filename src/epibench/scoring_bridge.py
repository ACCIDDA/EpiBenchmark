"""Bridge between the Python package and R scoringutils functionality."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

R_SCORING_SCRIPT = """#!/usr/bin/env Rscript
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2) {
  stop("Usage: Rscript score_with_scoringutils.R <input_csv> <output_csv>")
}

input_csv <- args[1]
output_csv <- args[2]

suppressPackageStartupMessages(library(scoringutils))

df <- read.csv(input_csv, stringsAsFactors = FALSE)
df$target_end_date <- as.Date(df$target_end_date)

forecast_object <- as_forecast_quantile(
  df,
  forecast_unit = c("model", "reference_date", "target_end_date", "location", "horizon"),
  observed = "observed",
  predicted = "predicted",
  quantile = "quantile_level"
)

scores <- score(forecast_object)
write.csv(scores, output_csv, row.names = FALSE)
"""


class ScoringBridge:
    """Run scoringutils via an external Rscript process."""

    def __init__(self, rscript_executable: str | None = None):
        self.rscript_executable = rscript_executable or shutil.which("Rscript")
        if not self.rscript_executable:
            raise RuntimeError(
                "Could not find `Rscript` on PATH. Install R and ensure `Rscript` is available."
            )

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
                if "there is no package called ‘scoringutils’" in details or "there is no package called 'scoringutils'" in details:
                    raise RuntimeError(
                        "R scoring process failed because the R package `scoringutils` is not installed.\n"
                        "Install it in R with:\n"
                        "Rscript -e 'install.packages(\"scoringutils\")'"
                    )
                raise RuntimeError(
                    "R scoring process failed."
                    + (f"\n{details}" if details else "")
                )

            if not output_path.exists():
                raise RuntimeError("R scoring process completed without producing an output file.")

            logger.info("Success ✅")
            return pd.read_csv(output_path)
