# API reference

Programmatic entry points behind the [challenge library commands](getting-started/challenge-library.md).

## `epibench.library`

`all_challenges() -> dict[str, dict]`
: Return `{challenge_id: definition}` for every challenge JSON in the bundled library, sorted by id.

`load_challenge(challenge_id: str) -> dict`
: Load one challenge definition by id; raises if the id is not in the library.

`is_published(definition: dict) -> bool`
: `True` when a challenge has a real Zenodo DOI (i.e. data available to download).

## `epibench.fetch`

`fetch(challenge_id: str, output_path: str | None = None) -> None`
: Download a challenge's data files from Zenodo into `<output_path>/<challenge_id>/` (defaults to the current directory), unzipping archives and keeping a copy of the challenge definition.
