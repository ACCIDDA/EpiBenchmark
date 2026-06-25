"""Start of the `make-scorecard` pipeline."""

from __future__ import annotations

import json
import logging
from importlib import resources

import click

from .config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_library_challenges() -> dict[str, object]:
    """Load the bundled EpiBenchmark challenge library."""
    challenges_path = resources.files("epibench").joinpath(
        "challenges-library", "challenges.json"
    )
    with challenges_path.open("r", encoding="utf-8") as challenges_file:
        return json.load(challenges_file)


def make_scorecard(
    challenge_name: str | None = None,
    model_data_path: str | None = None,
    config_path: str | None = None,
) -> None:
    """
    Main execution function for the epibench make-scorecard pipeline.
    """
    using_library_challenge = challenge_name is not None or model_data_path is not None
    using_config = config_path is not None

    # fail if --config-path AND --model-data-path are passed in the same command
    logger.info("Validating make-scorecard inputs...")
    if using_library_challenge and using_config:
        raise click.UsageError(
            "Use either a library challenge with --model-data-path or --config-path, not both."
        )

    # if using a config (not a pre-made EpiBenchmark challenge)
    if using_config:
        if challenge_name is not None or model_data_path is not None:
            raise click.UsageError(
                "When using --config-path, do not provide challenge-name or --model-data-path."
            )
        logger.info("Validating config file...")
        config_object = Config(config_path=config_path, pipeline="make-scorecard")
        # TODO, score given model, call unique scorecard function, return score csv and score card entry for given model
        pass

    # fail if user doesn't provide anything with `epibench make-scorecard`
    elif challenge_name is None and model_data_path is None:
        raise click.UsageError(
            "Provide either <challenge-name> with --model-data-path or --config-path."
        )
    # fail if user doesn't provide the challenge name
    elif challenge_name is None:
        raise click.UsageError(
            "A library challenge name is required when using --model-data-path."
        )
    # fail if user doesn't provide --model-data-path
    elif model_data_path is None:
        raise click.UsageError(
            "--model-data-path is required when using a library challenge."
        )
    else:
        logger.info("Loading challenge library...")
        library_challenges = _load_library_challenges()
        if challenge_name not in library_challenges:
            raise click.ClickException(
                "that challenge is not in the EpiBenchmark challenge library"
            )
        logger.info(f"Successfully loaded library challenge: {challenge_name} ✅")
        # TODO, score given model, call unique scorecard function, return score csv and score card entry for given model
        pass

    logger.info("make-scorecard skeleton completed successfully.")
