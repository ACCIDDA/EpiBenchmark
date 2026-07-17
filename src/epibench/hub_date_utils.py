"""Helper functions for hub schedule metadata and setup-date validation."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from importlib import resources
from pathlib import Path

logger = logging.getLogger(__name__)


def _normalize_hub_name(hub_path: Path) -> str:
    """Map a resolved hub path to the key used in the bundled date library."""
    return hub_path.name.strip().lower()


def load_hub_date_library() -> dict[str, dict[str, dict[str, str]]]:
    """Load the bundled hub season date library."""
    hub_dates_resource = resources.files("epibench").joinpath(
        "hub-dates-library", "hub_dates.json"
    )
    with hub_dates_resource.open("r", encoding="utf-8") as hub_dates_file:
        return json.load(hub_dates_file)


def _parse_season_bounds(
    hub_name: str,
    season_name: str,
    season_bounds: dict[str, str],
) -> tuple[datetime.date, datetime.date]:
    """Parse a season's inclusive start/end dates from the bundled library."""
    try:
        season_start = datetime.strptime(season_bounds["start"], "%Y-%m-%d").date()
        season_end = datetime.strptime(season_bounds["end"], "%Y-%m-%d").date()
    except KeyError as exc:
        raise KeyError(
            f"Season {season_name!r} for hub {hub_name!r} is missing a required "
            f"date key in hub_dates.json: {exc}"
        ) from exc
    except ValueError as exc:
        raise ValueError(
            f"Season {season_name!r} for hub {hub_name!r} has invalid dates in "
            f"hub_dates.json. Dates must be YYYY-MM-DD. Error: {exc}"
        ) from exc

    if season_start > season_end:
        raise ValueError(
            f"Season {season_name!r} for hub {hub_name!r} has start date after end date "
            "in hub_dates.json."
        )
    return season_start, season_end


def _derive_gt_cutoff_dates(
    requested_dates: list[str],
    offset_days: int,
) -> list[str]:
    """
    Derive truth cutoff dates from setup/reference dates.

    ``offset_days`` is applied directly to each requested date:
    - ``0`` keeps the cutoff date aligned with the requested date
    - negative values move the cutoff earlier
    - positive values move the cutoff later
    """
    return [
        (
            datetime.strptime(requested_date, "%Y-%m-%d").date()
            + timedelta(days=offset_days)
        ).strftime("%Y-%m-%d")
        for requested_date in requested_dates
    ]


def _warn_on_vintaging_offset_mismatch(hub_path: Path, vintaging_cutoff: int) -> None:
    """
    Logs a warning to the user if:
        - the configured vintaging cutoff cannot be verified against hub tasks.json file
          because the file/keys cannot be found
        - the configured vintaging cutoff does not match a hubs' set submissions_due 'end' key

    Silent success if the required file/keys are found and the submissions_due 'end'
    key matches the configured vintaging cutoff.

    This checks ``hub-config/tasks.json`` for any nested ``submissions_due`` blocks and
    compares their nested ``end`` values against the supplied ``vintaging_cutoff``.
    """

    def _find_nested_values(payload: object, target_key: str) -> list[object]:
        """Return all values found for ``target_key`` anywhere in a nested JSON payload."""
        matches: list[object] = []
        if isinstance(payload, dict):
            for key, value in payload.items():
                if key == target_key:
                    matches.append(value)
                matches.extend(_find_nested_values(value, target_key))
        elif isinstance(payload, list):
            for item in payload:
                matches.extend(_find_nested_values(item, target_key))
        return matches

    tasks_json_path = hub_path / "hub-config" / "tasks.json"

    # warn if we cannot find tasks.json
    if not tasks_json_path.is_file():
        logger.warning(
            "Could not cross-check vintaging cutoff %s against hub metadata because "
            "%s was not found. Proceeding with processing.",
            vintaging_cutoff,
            tasks_json_path,
        )
        return

    # warn if we found but could not load tasks.json
    try:
        with tasks_json_path.open("r", encoding="utf-8") as tasks_json_file:
            tasks_payload = json.load(tasks_json_file)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Could not cross-check vintaging cutoff %s against hub metadata because "
            "%s could not be read: %s. Proceeding with processing.",
            vintaging_cutoff,
            tasks_json_path,
            exc,
        )
        return

    # warn if we found tasks.json but could not find 'submissions_due' key
    submissions_due_blocks = _find_nested_values(tasks_payload, "submissions_due")
    if not submissions_due_blocks:
        logger.warning(
            "Could not cross-check vintaging cutoff %s against hub metadata because "
            "no 'submissions_due' key was found in %s. Proceeding with processing.",
            vintaging_cutoff,
            tasks_json_path,
        )
        return

    # warn if we could not find 'end' key
    end_values: list[object] = []
    for submissions_due_block in submissions_due_blocks:
        end_values.extend(_find_nested_values(submissions_due_block, "end"))
    if not end_values:
        logger.warning(
            "Could not cross-check vintaging cutoff %s against hub metadata because "
            "no nested 'end' key was found under 'submissions_due' in %s. Proceeding with processing.",
            vintaging_cutoff,
            tasks_json_path,
        )
        return

    # warn if everything was found, but value did not match configured cutoff 
    if vintaging_cutoff not in end_values:
        logger.warning(
            "Please note that configured vintaging cutoff %s does not match the hub metadata in %s. "
            "Found submissions_due.end value(s): %s. Proceeding with processing.",
            vintaging_cutoff,
            tasks_json_path,
            sorted(set(end_values), key=str),
        )


def validate_setup_dates_against_hub_rounds(
    hub_path: Path,
    requested_dates: list[str],
    targets: list[str],
    gt_cutoff_offset: int,
) -> tuple[list[str], list[str], str | None]:
    """
    Validate setup dates against bundled hub season boundaries.

    Rules:
    - the hub must appear in the bundled date library, otherwise validation is skipped
    - all requested dates must belong to exactly one listed season
    - each requested date must be a 7-day multiple from that season's start date

    Returns:
    - validated setup dates
    - gt cutoff dates derived from each setup date plus ``gt_cutoff_offset``
    - matched season label, if validation was possible
    """
    del targets  # date validation now relies only on bundled hub season metadata
    _warn_on_vintaging_offset_mismatch(
        hub_path=hub_path,
        vintaging_cutoff=gt_cutoff_offset,
    )

    hub_name = _normalize_hub_name(hub_path)
    hub_date_library = load_hub_date_library()

    if hub_name not in hub_date_library:
        logger.warning(
            "Hub %s was not found in bundled hub_dates.json. Proceeding without "
            "validating setup dates against the hard-coded season library.",
            hub_name,
        )
        return (
            requested_dates,
            _derive_gt_cutoff_dates(requested_dates, offset_days=gt_cutoff_offset),
            None,
        )

    season_matches: list[str] = []
    requested_date_objects = [
        datetime.strptime(requested_date, "%Y-%m-%d").date()
        for requested_date in requested_dates
    ]

    for season_name, season_bounds in hub_date_library[hub_name].items():
        season_start, season_end = _parse_season_bounds(
            hub_name=hub_name,
            season_name=season_name,
            season_bounds=season_bounds,
        )

        if all(season_start <= requested_date <= season_end for requested_date in requested_date_objects):
            season_matches.append(season_name)

    if not season_matches:
        raise ValueError(
            "Requested setup dates do not fall within a single season listed in "
            f"hub_dates.json for hub {hub_name!r}."
        )

    if len(season_matches) > 1:
        raise ValueError(
            "Requested setup dates match more than one season in hub_dates.json for "
            f"hub {hub_name!r}: {season_matches}. Please limit each setup run to one season."
        )

    matched_season_name = season_matches[0]
    matched_season_start, _ = _parse_season_bounds(
        hub_name=hub_name,
        season_name=matched_season_name,
        season_bounds=hub_date_library[hub_name][matched_season_name],
    )

    invalid_dates = [
        requested_date.strftime("%Y-%m-%d")
        for requested_date in requested_date_objects
        if (requested_date - matched_season_start).days % 7 != 0
    ]
    if invalid_dates:
        raise ValueError(
            "The following setup dates are not weekly multiples of the season start "
            f"date {matched_season_start} for hub {hub_name!r}, season {matched_season_name!r}: "
            f"{invalid_dates}"
        )

    return (
        requested_dates,
        _derive_gt_cutoff_dates(requested_dates, offset_days=gt_cutoff_offset),
        matched_season_name,
    )
