"""Skeleton implementation for the `epibench make-scorecard` pipeline."""

from __future__ import annotations

import json
from importlib import resources

import click


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
    """Dispatch scorecard generation from either a library challenge or a config."""
    using_library_challenge = challenge_name is not None or model_data_path is not None
    using_config = config_path is not None

    if using_library_challenge and using_config:
        raise click.UsageError(
            "Use either a library challenge with --model-data-path or --config-path, not both."
        )

    if using_config:
        if challenge_name is not None or model_data_path is not None:
            raise click.UsageError(
                "When using --config-path, do not provide challenge-name or --model-data-path."
            )
        # Placeholder for future config-based scorecard generation.
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

    library_challenges = _load_library_challenges()
    if challenge_name not in library_challenges:
        raise click.ClickException(
            "that challenge is not in the EpiBenchmark challenge library"
        )

    # Placeholder for future library-challenge scorecard generation.
    return
