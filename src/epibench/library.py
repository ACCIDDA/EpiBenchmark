"""Helpers for reading the bundled EpiBenchmark challenge library."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import TypedDict

import click

# temp `zenodo_doi` values for challenges that aren't on Zenodo yet; ideally will be removed later
_UNPUBLISHED_DOI_VALUES = {"", "tbd"}
_UNPUBLISHED_DATA_LABEL = "Not yet published to Zenodo"


class ChallengeInfo(TypedDict):
    """Public summary fields for one challenge-library entry."""

    hub: str
    target: str
    dates: list[str]
    data: str


def all_challenges() -> dict[str, dict]:
    """Return ``{challenge_id: definition}`` for every JSON in the library, sorted by id."""
    challenges_dir = resources.files("epibench").joinpath("challenges-library")
    files = sorted(
        (p for p in challenges_dir.iterdir() if p.suffix.lower() == ".json"),
        key=lambda p: p.stem,
    )
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in files}


def list_challenges() -> list[dict[str, ChallengeInfo]]:
    """Return public summary information for each challenge in the EpiBenchmark library.

    Each list item has one key containing the challenge name. Its value
    contains the hub, target, included reference dates, and Zenodo availability.
    """
    challenges = []
    for challenge_id, definition in all_challenges().items():
        dates = definition.get("reference_dates") or []
        data = (
            str(definition["zenodo_doi"])
            if is_published(definition)
            else _UNPUBLISHED_DATA_LABEL
        )
        challenges.append(
            {
                challenge_id: {
                    "hub": str(definition.get("hub", "?")),
                    "target": str(definition.get("target", "?")),
                    "dates": [str(reference_date) for reference_date in dates],
                    "data": data,
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


def is_published(definition: dict) -> bool:
    """True when the challenge has a real Zenodo DOI (i.e. data to download)."""
    doi = definition.get("zenodo_doi")
    return isinstance(doi, str) and doi.strip().lower() not in _UNPUBLISHED_DOI_VALUES


def print_challenge_list() -> None:
    """Print every challenge in the library with its data-availability status."""
    challenges = list_challenges()
    if not challenges:
        click.echo("No challenges found in the EpiBenchmark library.")
        return

    click.echo(f"Available EpiBenchmark challenges ({len(challenges)}):\n")
    for challenge in challenges:
        challenge_id, info = next(iter(challenge.items()))
        dates = info["dates"]
        date_span = f"{dates[0]} → {dates[-1]} ({len(dates)} dates)" if dates else "no reference dates"
        status = (
            f"zenodo: {info['data']}"
            if info["data"] != _UNPUBLISHED_DATA_LABEL
            else "data not yet published to Zenodo"
        )
        click.echo(click.style(f"  {challenge_id}", bold=True))
        click.echo(f"      hub:    {info['hub']}")
        click.echo(f"      target: {info['target']}")
        click.echo(f"      dates:  {date_span}")
        click.echo(f"      {status}")
        click.echo("")
