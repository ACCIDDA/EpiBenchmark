"""Helpers for reading the bundled EpiBenchmark challenge library."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

import click

# `zenodo_doi` values that mean "no data has been published yet".
_UNPUBLISHED_DOI_VALUES = {"", "tbd"}


def all_challenges() -> dict[str, dict]:
    """Return ``{challenge_id: definition}`` for every JSON in the library, sorted by id."""
    challenges_dir = resources.files("epibench").joinpath("challenges-library")
    files = sorted(
        (p for p in challenges_dir.iterdir() if p.suffix.lower() == ".json"),
        key=lambda p: p.stem,
    )
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in files}


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
    challenges = all_challenges()
    if not challenges:
        click.echo("No challenges found in the EpiBenchmark library.")
        return

    click.echo(f"Available EpiBenchmark challenges ({len(challenges)}):\n")
    for challenge_id, definition in challenges.items():
        dates = definition.get("reference_dates") or []
        date_span = f"{dates[0]} → {dates[-1]} ({len(dates)} dates)" if dates else "no reference dates"
        status = (
            f"zenodo: {definition['zenodo_doi']}"
            if is_published(definition)
            else "data not yet published to Zenodo"
        )
        click.echo(click.style(f"  {challenge_id}", bold=True))
        click.echo(f"      hub:    {definition.get('hub', '?')}")
        click.echo(f"      target: {definition.get('target', '?')}")
        click.echo(f"      dates:  {date_span}")
        click.echo(f"      {status}")
        click.echo("")
