"""Start of the `score` pipeline."""

from __future__ import annotations

import json
import logging
from importlib import resources
from pathlib import Path

import click
import pandas as pd

from .config import Config
from .extract_model_data_details import extract_model_data_details
from .ground_truth import GroundTruth
from .gt_from_hub import hub_clone_setup
from .path_utils import resolve_path
from .scorecard_functions import custom_scorecard
from .scoring_bridge import ScoringBridge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCORES_FILENAME = "EpiBenchmark_scores.csv" # TODO, will be changed with hash, shoudl be challenge-name
SCORECARD_FILENAME = "EpiBenchmark_scorecard.csv" # TODO, will be changed with hash, should be challenge-name


def _load_library_challenges() -> dict[str, object]:
    """Load the EpiBenchmark challenge library (challenges.json)."""
    challenges_path = resources.files("epibench").joinpath(
        "challenges-library", "challenges.json"
    )
    with challenges_path.open("r", encoding="utf-8") as challenges_file:
        return json.load(challenges_file)


def _score_models(
    hub_path: Path,
    model_info: dict[str, list[Path]],
    include_models: list[str],
    evaluation_start_date,
    evaluation_end_date,
    target: str,
    baseline_model: str,
) -> pd.DataFrame:
    """Run scoringutils (R) and return the resulting score table."""
    logger.info("Validating model data...")
    model_dict, locations_list = extract_model_data_details(
        hub_path=hub_path,
        model_info=model_info,
        include_models=include_models,
        eval_start_date=evaluation_start_date,
        eval_end_date=evaluation_end_date,
        target=target,
    )

    logger.info("Retrieving and formatting ground truth data...")
    gto = GroundTruth(
        hub_path=hub_path,
        target=target,
        locations=locations_list,
        eval_start_date=evaluation_start_date,
        eval_end_date=evaluation_end_date,
    )

    df = pd.concat(model_dict.values(), ignore_index=True)
    df = df.merge(gto.gt, on=["target", "target_end_date", "location"]).drop(
        columns=["target"]
    )

    logger.info("Scoring model data...")
    scorer = ScoringBridge(baseline_model=baseline_model)
    return scorer.score_forecasts(df)


def _write_scores(scores: pd.DataFrame, output_dir: Path) -> Path:
    """Write scores to disk and return the output path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    full_output_path = output_dir / SCORES_FILENAME
    if full_output_path.exists(): # does not overwrite
        raise FileExistsError(
            f"Score output file already exists and will not be overwritten: {full_output_path}"
        )
    scores.to_csv(full_output_path, index=False, encoding="utf-8-sig")
    return full_output_path


def _write_scorecard(scorecard_results: dict[str, object], output_dir: Path) -> Path:
    """Write scorecard results to disk and return the output path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    scorecard_output_path = output_dir / SCORECARD_FILENAME
    if scorecard_output_path.exists(): # does not overwrite
        raise FileExistsError(
            "Scorecard output file already exists and will not be overwritten: "
            f"{scorecard_output_path}"
        )
    scorecard_df = pd.DataFrame(
        [
            {"metric": metric_name, "value": metric_value}
            for metric_name, metric_value in scorecard_results.items()
        ]
    )
    scorecard_df.to_csv(scorecard_output_path, index=False, encoding="utf-8-sig")
    return scorecard_output_path


def _resolve_model_info(model_data_path: str) -> tuple[dict[str, list[Path]], Path]:
    """Normalize a library-route model path into the model_info shape used by scoring."""
    resolved_model_data_path = resolve_path(model_data_path)
    # fail if it does not exist
    if not resolved_model_data_path.exists():
        raise FileNotFoundError(
            f"--model-data-path {resolved_model_data_path} does not exist."
        )
    # fail if it is a file but not a .csv
    if resolved_model_data_path.is_file():
        if resolved_model_data_path.suffix.lower() != ".csv":
            raise ValueError(
                "--model-data-path must point to a .csv file or a directory of .csv files."
            )
        model_name = resolved_model_data_path.stem
        model_info = {model_name: [resolved_model_data_path]}
    # fail if it is a dir with no .csvs
    elif resolved_model_data_path.is_dir():
        csv_paths = sorted(resolved_model_data_path.glob("*.csv"))
        if not csv_paths:
            raise ValueError(
                f"No CSV files were found at --model-data-path {resolved_model_data_path}."
            )
        model_name = resolved_model_data_path.name
        model_info = {model_name: csv_paths}
    # fail if neither dir nor .csv
    else:
        raise ValueError(
            "--model-data-path must point to a .csv file or a directory of .csv files."
        )

    return model_info, resolved_model_data_path


def _resolve_output_dir(output_path: str) -> Path:
    """Resolve and validate a library-route output directory."""
    resolved_output_path = resolve_path(output_path)
    if resolved_output_path.exists() and not resolved_output_path.is_dir():
        raise NotADirectoryError(
            f"--output-path must be a directory. Received {resolved_output_path}"
        )
    resolved_output_path.mkdir(parents=True, exist_ok=True)
    return resolved_output_path


def _score_from_config(config_path: str) -> None:
    """Run the config-driven scoring workflow (just CSV; no scorecard made)"""
    logger.info("Validating config...")
    config_object = Config(config_path=config_path, pipeline="score")

    scores = _score_models(
        hub_path=config_object.hub_path,
        model_info=config_object.model_info,
        include_models=config_object.include_models,
        evaluation_start_date=config_object.evaluation_start_date,
        evaluation_end_date=config_object.evaluation_end_date,
        target=config_object.target,
        baseline_model=config_object.baseline_model,
    )

    full_output_path = _write_scores(scores, config_object.output_path)
    logger.info("Process executed successfully to end 🎉.")
    logger.info(f"Output file at {full_output_path}")


def score_from_challenge_library(
    challenge_name: str,
    model_data_path: str,
    output_path: str,
) -> None:
    """Run challenge library scoring (scores CSV + scorecard)"""

    # fail if provided challenge is not in our library
    logger.info("Loading challenge library...")
    library_challenges = _load_library_challenges()
    library_challenge_entries = library_challenges.get("challenges", {})
    if challenge_name not in library_challenge_entries:
        raise click.ClickException(
            "that challenge is not in the EpiBenchmark challenge library"
        )
    challenge_definition = library_challenge_entries[challenge_name]
    logger.info(f"Successfully loaded library challenge: {challenge_name} ✅")

    # TODO, verify what _resolve_model_info() does 
    model_info, _ = _resolve_model_info(model_data_path)
    output_dir = _resolve_output_dir(output_path)

    # set target 
    target = str(challenge_definition["target"])

    # set eval start and end
    challenge_target_end_dates = challenge_definition.get("target_end_dates", [])
    evaluation_start_date = pd.to_datetime(min(challenge_target_end_dates))
    evaluation_end_date = pd.to_datetime(max(challenge_target_end_dates))

    # ensure hub clone
    hub_path = hub_clone_setup(hub_url=challenge_definition["hub_path"])

    # set baseline model, add to include models list
    baseline_model = challenge_definition["basline_model"]
    include_models = [baseline_model]

    # send to general scoring function (to be sent to R scoringutils)
    scores = _score_models(
        hub_path=hub_path,
        model_info=model_info,
        include_models=include_models,
        evaluation_start_date=evaluation_start_date,
        evaluation_end_date=evaluation_end_date,
        target=target,
        baseline_model=baseline_model,
    )

    score_output_path = _write_scores(scores, output_dir)
    logger.info(f"Output file at {score_output_path}")

    # build scorecard using custom function registry
    scorecard_results = custom_scorecard(
        challenge_definition["scorecard_function"],
        score_file=scores,
    )
    scorecard_output_path = _write_scorecard(scorecard_results, output_dir)
    logger.info(f"Scorecard output file at {scorecard_output_path}")


def score(
    challenge_name: str | None = None,
    model_data_path: str | None = None,
    output_path: str | None = None,
    config_path: str | None = None,
) -> None:
    """
    Main execution function for the `epibench score` pipeline.
    """
    using_library_challenge = challenge_name is not None or model_data_path is not None
    using_config = config_path is not None

    logger.info("Validating score inputs...")
    # fail if both --model-data-path and --config-path are provided
    if using_library_challenge and using_config:
        raise click.UsageError("Use either a library challenge with --model-data-path or --config-path, not both.")

    if using_config:
        # fail if challenge name or --model-data-path is given with --config-path
        if (
            challenge_name is not None
            or model_data_path is not None
            or output_path is not None
        ):
            raise click.UsageError(
                "When using --config-path, do not provide challenge-name, "
                "--model-data-path, or --output-path."
            )
        # othwerise, score normally
        _score_from_config(config_path=config_path)
        return

    # fail if no --model-data-path, challenge name, OR --config-path
    if challenge_name is None and model_data_path is None:
        raise click.UsageError(
            "Provide either <challenge-name> with --model-data-path or --config-path."
        )
    # fail if no challenge name with --model-data-path
    if challenge_name is None:
        raise click.UsageError(
            "A library challenge name is required when using --model-data-path."
        )
    # fail if no --model-path with challenge name
    if model_data_path is None:
        raise click.UsageError(
            "--model-data-path is required when using a library challenge."
        )
    # fail if no --output-path wih challenge name
    if output_path is None:
        raise click.UsageError(
            "--output-path is required when using a library challenge."
        )
    # otherwise, score score normally + build scorecard 
    score_from_challenge_library(
        challenge_name=challenge_name,
        model_data_path=model_data_path,
        output_path=output_path,
    )
    logger.info("Process executed successfully to end 🎉.")
