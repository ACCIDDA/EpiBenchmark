"""Run the `plot` pipeline and export a PDF of summary figures."""

from __future__ import annotations

import logging

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from .build_plots import build_summary_figures, load_scores
from .config import Config


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def plot(config_path: str | None = None) -> None:
    """
    Main execution function for the `epibench plot` pipeline.
    """
    logger.info("Validating config...")
    config_object = Config(config_path=config_path, pipeline="plot")

    logger.info("Loading and validating scoring output...")
    score_df = load_scores(config_object.score_file_path)

    logger.info("Building figures...")
    figures = build_summary_figures(score_df)

    output_pdf = config_object.plot_output_dir / "EpiBenchmark_plots.pdf"
    logger.info("Writing PDF to %s", output_pdf)
    with PdfPages(output_pdf) as pdf:
        for figure in figures:
            pdf.savefig(figure, bbox_inches="tight")
            plt.close(figure)

    logger.info("File executed successfully to end.")
    logger.info("Output file at %s", output_pdf)
