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
from .path_utils import resolve_hub_path, resolve_path
from .scorecard_functions import custom_scorecard
from .scoring_bridge import ScoringBridge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LIBRARY_BASELINE_FALLBACK = "__epibench_library_baseline__"
SCORES_FILENAME = "EpiBenchmark_scores.csv" # TODO, will be changed with hash
SCORECARD_FILENAME = "EpiBenchmark_scorecard.csv" # TODO, will be changed with hash


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
    if not resolved_model_data_path.exists():
        raise FileNotFoundError(
            f"--model-data-path {resolved_model_data_path} does not exist."
        )

    if resolved_model_data_path.is_file():
        if resolved_model_data_path.suffix.lower() != ".csv":
            raise ValueError(
                "--model-data-path must point to a .csv file or a directory of .csv files."
            )
        model_name = resolved_model_data_path.stem
        model_info = {model_name: [resolved_model_data_path]}
    elif resolved_model_data_path.is_dir():
        csv_paths = sorted(resolved_model_data_path.glob("*.csv"))
        if not csv_paths:
            raise ValueError(
                f"No CSV files were found at --model-data-path {resolved_model_data_path}."
            )
        model_name = resolved_model_data_path.name
        model_info = {model_name: csv_paths}
    else:
        raise ValueError(
            "--model-data-path must point to a .csv file or a directory of .csv files."
        )

    return model_info, resolved_model_data_path


def _infer_target_and_eval_window(model_info: dict[str, list[Path]]) -> tuple[str, pd.Timestamp, pd.Timestamp]:
    """Infer target and evaluation date range from the provided model data."""
    discovered_targets: set[str] = set()
    target_end_dates: list[pd.Timestamp] = []

    for csv_paths in model_info.values():
        for csv_path in csv_paths:
            df = pd.read_csv(csv_path, usecols=["target", "target_end_date"])
            if df.empty:
                continue
            discovered_targets.update(df["target"].dropna().astype(str).unique())
            dates = pd.to_datetime(df["target_end_date"], errors="coerce").dropna()
            target_end_dates.extend(dates.tolist())

    if not discovered_targets:
        raise ValueError("Could not determine a target from the provided model data.")
    if len(discovered_targets) > 1:
        raise ValueError(
            "Provided model data contains more than one unique target. "
            "Library challenge scoring currently supports only one target per run."
        )
    if not target_end_dates:
        raise ValueError(
            "Could not determine evaluation dates from the provided model data."
        )

    inferred_target = next(iter(discovered_targets))
    return inferred_target, min(target_end_dates), max(target_end_dates)


def _resolve_library_hub_path(
    challenge_name: str, challenge_definition: dict[str, object]
) -> Path:
    """Resolve the hub path for a library challenge."""
    if "hub_path" not in challenge_definition or not challenge_definition["hub_path"]:
        raise ValueError(
            f"Challenge {challenge_name} is missing required field `hub_path` "
            "in the EpiBenchmark challenge library."
        )

    try:
        return resolve_hub_path(str(challenge_definition["hub_path"]))
    except ValueError as exc:
        raise ValueError(
            f"Challenge {challenge_name} has an invalid `hub_path`. {exc}"
        ) from exc


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
    logger.info("File executed successfully to end 🎉.")
    logger.info(f"Output file at {full_output_path}")


def _score_from_library_challenge(challenge_name: str, model_data_path: str) -> None:
    """Run library-challenge scoring (scores CSV + scorecard)"""
    logger.info("Loading challenge library...")
    library_challenges = _load_library_challenges()
    library_challenge_entries = library_challenges.get("challenges", {})
    if challenge_name not in library_challenge_entries:
        raise click.ClickException(
            "that challenge is not in the EpiBenchmark challenge library"
        )

    challenge_definition = library_challenge_entries[challenge_name]
    logger.info(f"Successfully loaded library challenge: {challenge_name} ✅")

    model_info, resolved_model_data_path = _resolve_model_info(model_data_path)
    inferred_target, inferred_start_date, inferred_end_date = _infer_target_and_eval_window(
        model_info
    )

    target = str(challenge_definition.get("target", inferred_target))
    challenge_target_dates = challenge_definition.get("target_dates", [])
    if challenge_target_dates:
        evaluation_start_date = pd.to_datetime(min(challenge_target_dates))
        evaluation_end_date = pd.to_datetime(max(challenge_target_dates))
    else:
        evaluation_start_date = inferred_start_date
        evaluation_end_date = inferred_end_date

    hub_path = _resolve_library_hub_path(challenge_name, challenge_definition)
    baseline_model = str(
        challenge_definition.get("baseline_model", LIBRARY_BASELINE_FALLBACK)
    )
    include_models = list(challenge_definition.get("include_models", []))
    if baseline_model != LIBRARY_BASELINE_FALLBACK and baseline_model not in include_models:
        include_models.append(baseline_model)

    scores = _score_models(
        hub_path=hub_path,
        model_info=model_info,
        include_models=include_models,
        evaluation_start_date=evaluation_start_date,
        evaluation_end_date=evaluation_end_date,
        target=target,
        baseline_model=baseline_model,
    )

    output_dir = resolved_model_data_path.parent if resolved_model_data_path.is_file() else resolved_model_data_path
    score_output_path = _write_scores(scores, output_dir)
    logger.info(f"Output file at {score_output_path}")

    scorecard_results = custom_scorecard(
        challenge_definition.get("scorecard_function", []),
        score_file=scores,
    )
    scorecard_output_path = _write_scorecard(scorecard_results, output_dir)
    logger.info(f"Scorecard output file at {scorecard_output_path}")


def score(
    challenge_name: str | None = None,
    model_data_path: str | None = None,
    config_path: str | None = None,
) -> None:
    """
    Main execution function for the `epibench score` pipeline.
    """
    using_library_challenge = challenge_name is not None or model_data_path is not None
    using_config = config_path is not None

    logger.info("Validating score inputs...")
    if using_library_challenge and using_config:
        raise click.UsageError(
            "Use either a library challenge with --model-data-path or --config-path, not both."
        )

    if using_config:
        if challenge_name is not None or model_data_path is not None:
            raise click.UsageError(
                "When using --config-path, do not provide challenge-name or --model-data-path."
            )
        _score_from_config(config_path=config_path)
        return

    if challenge_name is None and model_data_path is None:
        raise click.UsageError(
            "Provide either <challenge-name> with --model-data-path or --config-path."
        )
    if challenge_name is None:
        raise click.UsageError(
            "A library challenge name is required when using --model-data-path."
        )
    if model_data_path is None:
        raise click.UsageError(
            "--model-data-path is required when using a library challenge."
        )

    _score_from_library_challenge(
        challenge_name=challenge_name,
        model_data_path=model_data_path,
    )
    logger.info("Process executed successfully to end 🎉.")
