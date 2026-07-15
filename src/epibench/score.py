"""Start of the `score` pipeline."""

import json
import logging
from importlib import resources
from pathlib import Path
from typing import Literal

import click
import pandas as pd

from .config import Config
from .extract_model_data_details import extract_model_data_details
from .scoring_ground_truth import ScoringGroundTruth
from .setup_ground_truth import hub_clone_setup
from .path_utils import resolve_output_dir, resolve_path
from .quantile_validation import (
    validate_for_scoring_config_quantiles,
    validate_for_scoring_library_challenge_quantiles,
)
from .scorecard_functions import custom_scorecard
from .scoring_bridge import ScoringBridge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCORES_FILENAME = "EpiBenchmark_scores.csv" # TODO, will be changed with hash, shoudl be challenge-name
SCORECARD_FILENAME = "EpiBenchmark_scorecard.csv" # TODO, will be changed with hash, should be challenge-name


def _load_library_challenge(challenge_name: str) -> dict[str, object]:
    """Load one EpiBenchmark library challenge from the challenges-library directory."""
    challenges_dir = resources.files("epibench").joinpath("challenges-library")
    requested_name = Path(challenge_name).stem

    available_challenge_files = {
        challenge_path.stem: challenge_path
        for challenge_path in challenges_dir.iterdir()
        if challenge_path.is_file() and challenge_path.suffix.lower() == ".json"
    }

    challenge_path = available_challenge_files.get(requested_name)
    if challenge_path is None:
        available_challenge_names = ", ".join(sorted(available_challenge_files))
        raise click.ClickException(
            "that challenge is not in the EpiBenchmark challenge library. "
            f"Available challenges: {available_challenge_names}"
        )

    with challenge_path.open("r", encoding="utf-8") as challenges_file:
        return json.load(challenges_file)


def _write_output_csv(
    output_kind: Literal["scores", "scorecard"],
    output_data: pd.DataFrame | dict[str, object],
    output_dir: Path,
) -> Path:
    """
    Write scores or scorecard output to disk and return the output path.
    No overwrites.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    # name for score csv
    if output_kind == "scores":
        output_path = output_dir / SCORES_FILENAME
        output_df = output_data
        error_label = "Score"
    # name for scorecard csv
    else:
        output_path = output_dir / SCORECARD_FILENAME
        output_df = pd.DataFrame([output_data])
        error_label = "Scorecard"
    # no overwrites
    if output_path.exists():
        raise FileExistsError(f"{error_label} output file already exists and will not be overwritten: {output_path}")
    # ensure type coercion worked
    if not isinstance(output_df, pd.DataFrame):
        raise TypeError("Score output data must be a pandas DataFrame.")

    # save
    output_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path


def _resolve_model_info(
    model_data_path: str,
    model_name: str,
) -> tuple[str, dict[str, list[Path]], Path]:
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
        model_info = {model_name: [resolved_model_data_path]}
    # fail if it is a dir with no .csvs
    elif resolved_model_data_path.is_dir():
        csv_paths = sorted(resolved_model_data_path.glob("*.csv"))
        if not csv_paths:
            raise ValueError(
                f"No CSV files were found at --model-data-path {resolved_model_data_path}."
            )
        model_info = {model_name: csv_paths}
    # fail if neither dir nor .csv
    else:
        raise ValueError(
            "--model-data-path must point to a .csv file or a directory of .csv files."
        )

    return model_name, model_info, resolved_model_data_path


def _score_from_config(config_path: str) -> None:
    """Run the config-driven scoring workflow (just CSV; no scorecard made)"""
    logger.info("Validating config...")
    config_object = Config(config_path=config_path, pipeline="score")

    logger.info("Validating model data...")
    model_dict, locations_list = extract_model_data_details(
        hub_path=config_object.hub_path,
        model_info=config_object.model_info,
        include_models=config_object.include_models,
        eval_start_date=config_object.evaluation_start_date,
        eval_end_date=config_object.evaluation_end_date,
        target=config_object.target,
    )

    logger.info("Validating quantile structure...")
    validate_for_scoring_config_quantiles(model_dict)

    logger.info("Retrieving and formatting ground truth data...")
    gto = ScoringGroundTruth(
        hub_path=config_object.hub_path,
        target=config_object.target,
        locations=locations_list,
        eval_start_date=config_object.evaluation_start_date,
        eval_end_date=config_object.evaluation_end_date,
    )

    df = pd.concat(model_dict.values(), ignore_index=True)
    df = df.merge(gto.gt, on=["target", "target_end_date", "location"]).drop(
        columns=["target"]
    )

    logger.info("Scoring model data...")
    scorer = ScoringBridge(baseline_model=config_object.baseline_model)
    scores = scorer.score_forecasts(df)

    full_output_path = _write_output_csv("scores", scores, config_object.output_path)
    logger.info("Process executed successfully to end 🎉.")
    logger.info(f"Output file at {full_output_path}")


def _score_from_challenge_library(
    challenge_name: str,
    model_data_path: str,
    model_name: str,
    output_path: str,
) -> None:
    """Run challenge library scoring (scores CSV + scorecard)"""

    logger.info("Loading challenge library...")
    challenge_definition = _load_library_challenge(challenge_name)
    logger.info(f"Successfully loaded library challenge: {challenge_name} ✅")

    model_name, model_info, _ = _resolve_model_info(model_data_path, model_name)
    output_dir = resolve_output_dir(output_path)

    # set quantiles
    quantiles = challenge_definition["quantiles"]

    # set target
    target = str(challenge_definition["target"])

    # derive eval window (first ref date minus lowest horizon, last ref date plus highest horizon)
    challenge_reference_dates = challenge_definition.get("reference_dates")
    reference_date_series = pd.to_datetime(challenge_reference_dates)
    horizon_offsets = [
        pd.to_timedelta(int(horizon), unit="W")
        for horizon in challenge_definition["horizons"]
    ]
    evaluation_start_date = min(reference_date_series + min(horizon_offsets))
    evaluation_end_date = max(reference_date_series + max(horizon_offsets))

    # ensure hub clone
    hub_path = hub_clone_setup(hub_url=challenge_definition["hub_path"])

    # set baseline model, add to include models list
    baseline_model = challenge_definition["baseline_model"]
    include_models = [baseline_model]

    # validate input model data
    logger.info("Validating model data...")
    model_dict, locations_list = extract_model_data_details(
        hub_path=hub_path,
        model_info=model_info,
        include_models=include_models,
        eval_start_date=evaluation_start_date,
        eval_end_date=evaluation_end_date,
        target=target,
        required_reference_dates=challenge_reference_dates,
        required_locations=challenge_definition["locations"],
        required_horizons=challenge_definition["horizons"],
    )

    # validate quantiles
    logger.info("Validating quantile structure...")
    validate_for_scoring_library_challenge_quantiles(model_dict, quantiles)

    # fetch (unvintaged) gt data for scoring
    logger.info("Retrieving and formatting ground truth data...")
    gto = ScoringGroundTruth(
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

    # score and save scoring file
    logger.info("Scoring model data...")
    scorer = ScoringBridge(baseline_model=baseline_model)
    scores = scorer.score_forecasts(df)
    score_output_path = _write_output_csv("scores", scores, output_dir)
    logger.info(f"Output scoring file at {score_output_path}")

    # build scorecard using custom function registry (and save)
    scorecard_results = custom_scorecard(
        model_name=model_name,
        scorecard_function_names=challenge_definition["scorecard_function"],
        score_file=scores,
    )
    scorecard_output_path = _write_output_csv("scorecard", scorecard_results, output_dir)
    logger.info(f"Scorecard output file at {scorecard_output_path}")


def score(
    challenge_name: str | None = None,
    model_data_path: str | None = None,
    model_name: str | None = None,
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
            or model_name is not None
            or output_path is not None
        ):
            raise click.UsageError(
                "When using --config-path, do not provide challenge-name, "
                "--model-data-path, --model-name, or --output-path."
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
    if model_name is None:
        raise click.UsageError(
            "--model-name is required when using a library challenge."
        )
    # fail if no --output-path wih challenge name
    if output_path is None:
        raise click.UsageError(
            "--output-path is required when using a library challenge."
        )
    # otherwise, score score normally + build scorecard 
    _score_from_challenge_library(
        challenge_name=challenge_name,
        model_data_path=model_data_path,
        model_name=model_name,
        output_path=output_path,
    )
    logger.info("Process executed successfully to end 🎉.")
