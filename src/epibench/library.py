"""Helpers for reading the bundled EpiBenchmark challenge library."""

from __future__ import annotations

import json
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import TypedDict

import click


class ChallengeInfo(TypedDict):
    """Public summary fields for one challenge-library entry."""

    hub: str
    target: str
    dates: list[str]


def _challenge_resource_directory(challenge_id: str) -> Traversable:
    """Return the package-resource directory for one challenge id."""
    return (
        resources.files("epibench")
        .joinpath("challenges-library")
        .joinpath(challenge_id)
    )


def _challenge_definition_files():
    """Return bundled challenge definition files, sorted by challenge id."""
    challenges_dir = resources.files("epibench").joinpath("challenges-library")
    files = []
    for challenge_dir in challenges_dir.iterdir():
        if not challenge_dir.is_dir():
            continue
        definition_path = challenge_dir.joinpath(f"{challenge_dir.name}.json")
        if definition_path.is_file():
            files.append(definition_path)
    return sorted(files, key=lambda path: path.stem)


def all_challenges() -> dict[str, dict]:
    """Return ``{challenge_id: definition}`` for every bundled challenge."""
    files = _challenge_definition_files()
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in files}


def list_challenges() -> list[dict[str, ChallengeInfo]]:
    """Return public summary information for each challenge in the EpiBenchmark library.

    Each list item has one key containing the challenge name. Its value
    contains the hub, target, and included reference dates.
    """
    challenges = []
    for challenge_id, definition in all_challenges().items():
        dates = definition.get("reference_dates") or []
        challenges.append(
            {
                challenge_id: {
                    "hub": str(definition.get("hub", "?")),
                    "target": str(definition.get("target", "?")),
                    "dates": [str(reference_date) for reference_date in dates],
                }
            }
        )
    return challenges


def load_challenge(challenge_id: str) -> dict:
    """Load one challenge definition by id, or raise listing what is available."""
    challenges = all_challenges()
    try:
        return challenges[Path(challenge_id).stem]
    except KeyError:
        raise click.ClickException(
            f"'{challenge_id}' is not in the EpiBenchmark challenge library. "
            f"Available challenges: {', '.join(challenges)}"
        ) from None


def print_challenge_list() -> None:
    """Print summary information for every challenge in the library."""
    challenges = list_challenges()
    if not challenges:
        click.echo("No challenges found in the EpiBenchmark library.")
        return

    click.echo(f"Available EpiBenchmark challenges ({len(challenges)}):\n")
    for challenge in challenges:
        challenge_id, info = next(iter(challenge.items()))
        dates = info["dates"]
        date_span = (
            f"{dates[0]} → {dates[-1]} ({len(dates)} dates)"
            if dates
            else "no reference dates"
        )
        click.echo(click.style(f"  {challenge_id}", bold=True))
        click.echo(f"      hub:    {info['hub']}")
        click.echo(f"      target: {info['target']}")
        click.echo(f"      dates:  {date_span}")
        click.echo("")
