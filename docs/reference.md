# API reference

#### coming soon (out of date)

Programmatic entry points behind the [challenge library commands](challenge-information/challenges.md).

## `epibench.Challenge`

`notes: str | None`
: Notes from the bundled definition of a library challenge. Access them with
  `challenge.notes` after calling `epibench.fetch_challenge(...)`. This value is
  `None` for challenges created directly with `epibench.create(...)`.

## `epibench.library`

`all_challenges() -> dict[str, dict]`
: Return `{challenge_id: definition}` for every challenge JSON in the bundled library, sorted by id.

`load_challenge(challenge_id: str) -> dict`
: Load one challenge definition by id; raises if the id is not in the library.

`list_challenges() -> list[dict]`
: Return the `hub`, `target`, and `dates` summary fields for every challenge.

## `epibench.fetch`

`fetch(challenge_id: str, output_path: str | None = None) -> None`
: Copy a bundled challenge into `<output_path>/<challenge_id>/` (defaults to the current directory).
