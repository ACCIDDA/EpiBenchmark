"""Public Python API and shared implementation for EpiBenchmark plotting"""

from __future__ import annotations

from collections.abc import Iterable
import logging
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
import pandas as pd

from .build_plots import build_summary_figures, read_scores, validate_scores
from .load_library_challenge import load_library_challenge
from .path_utils import establish_hub_path, resolve_output_dir, resolve_path
from .prep_complete_models_for_plotting import prep_complete_models_for_plotting
from .scoring_logic import score_forecasts


logger = logging.getLogger(__name__)

PLOTS_FILENAME = "EpiBenchmark_plots.pdf"


def _load_score_file(score_file_path: str | Path) -> pd.DataFrame:
    """Resolve path and read a score CSV for a CLI plotting route."""
    resolved_score_file_path = resolve_path(score_file_path)
    if not resolved_score_file_path.exists():
        raise FileNotFoundError(f"Score file not found: {resolved_score_file_path}")
    if not resolved_score_file_path.is_file():
        raise ValueError(
            f"--score-file-path must be a file. Received: {resolved_score_file_path}"
        )

    logger.info("Loading scoring output...")
    return read_scores(resolved_score_file_path)


def _save_figures(
    figures: Iterable[Figure],
    output_dir: Path,
) -> Path:
    """Write figures to the preflighted standard PDF path."""
    output_pdf = output_dir / PLOTS_FILENAME
    logger.info("Writing PDF to %s", output_pdf)
    with PdfPages(output_pdf) as pdf:
        for figure in figures:
            pdf.savefig(figure, bbox_inches="tight")
            plt.close(figure)
    logger.info("Success ✅")
    logger.info("File executed successfully to end 🎉")
    logger.info("Output file at %s", output_pdf)
    return output_pdf


def plot(
    score_file: pd.DataFrame,
    output_path: str | Path | None = None,
) -> Path:
    """Load + validate scores, build summary figures, and save the PDF output.

    The destination defaults to the current working directory. Existing
    ``EpiBenchmark_plots.pdf`` files are never overwritten (FileExistsError fails and exits).
    """
    score_df = validate_scores(score_file)
    output_dir = resolve_output_dir(
        output_path or Path.cwd(),
        files_to_save=[PLOTS_FILENAME],
    )
    logger.info("Building figures...")
    figures = build_summary_figures(score_df)
    logger.info("Success ✅")
    return _save_figures(figures, output_dir)


def plot_challenge(
    challenge_name: str,
    score_file: pd.DataFrame,
    output_path: str | Path | None = None,
) -> Path:
    """Build and save challenge plots including the challenge comparison models.

    ``score_file`` must contain ≥ 1 submitted model and the baseline model (the baseline 
    does not count toward that limit). When plotting with a challenge, hub complete models are
    loaded and scored using the same workflow as the command-line interface.
    """
    logger.info("Loading challenge library...")
    challenge_definition = load_library_challenge(challenge_name)
    logger.info("Successfully loaded library challenge: %s ✅", challenge_name)

    users_scores = validate_scores(score_file)
    baseline_model = challenge_definition["baseline_model"]
    non_baseline_models = set(
        users_scores.loc[users_scores["model"] != baseline_model, "model"]
    )
    # necessary early-fail to prevent failure at later logic: users_model_name = next(iter(non_baseline_models))
    if len(non_baseline_models) != 1:
        raise ValueError(
            "Please supply scores for exactly one non-baseline model. "
            f"Received: {non_baseline_models} "
            f"(baseline model {baseline_model} does not count towards model total)."
        )
    users_model_name = next(iter(non_baseline_models))

    output_dir = resolve_output_dir(
        output_path or Path.cwd(),
        files_to_save=[PLOTS_FILENAME],
    )

    logger.info("Retrieving external model data...")
    hub_path = establish_hub_path(hub_path_value=challenge_definition["hub_path"])
    complete_models = list(challenge_definition["complete_models"])
    if users_model_name in complete_models:
        complete_models.remove(users_model_name)

    complete_models_data = prep_complete_models_for_plotting(
        hub_path=hub_path,
        complete_models=complete_models,
        baseline_model=baseline_model,
        valid_locations=challenge_definition["locations"],
        valid_quantiles=challenge_definition["quantiles"],
        valid_horizons=challenge_definition["horizons"],
        valid_reference_dates=challenge_definition["reference_dates"],
        valid_target=challenge_definition["target"],
    )

    complete_models_scores = score_forecasts(
        complete_models_data,
        baseline_model=baseline_model,
    )
    complete_models_scores = complete_models_scores[
        complete_models_scores["model"] != baseline_model
    ]

    combined_scores = pd.concat(
        [complete_models_scores, users_scores],
        ignore_index=True,
    )
    combined_scores["reference_date"] = pd.to_datetime(
        combined_scores["reference_date"],
        errors="raise",
    )

    logger.info("Building figures...")
    figures = build_summary_figures(combined_scores)
    logger.info("Success ✅")
    return _save_figures(figures, output_dir)


def _plot_from_score_file(
    score_file_path: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    """CLI adapter for plotting directly from a score CSV."""
    return plot(
        score_file=_load_score_file(score_file_path),
        output_path=output_path,
    )


def _plot_challenge_from_score_file(
    challenge_name: str,
    score_file_path: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    """CLI adapter for challenge plotting from a score CSV."""
    return plot_challenge(
        challenge_name=challenge_name,
        score_file=_load_score_file(score_file_path),
        output_path=output_path,
    )
