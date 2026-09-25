"""Helper functions for hub schedule metadata and create-date validation."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from importlib import resources
from pathlib import Path

logger = logging.getLogger(__name__)


def create_season_start(reference_date: date) -> date:
    """Return the July 1 start of the season containing a reference date."""
    start_year = reference_date.year if reference_date.month >= 7 else reference_date.year - 1
    return date(start_year, 7, 1)


def _normalize_hub_name(hub_path: Path) -> str:
    """Map a resolved hub path to the key used in the bundled date library."""
    return hub_path.name.strip().lower()


def load_hub_date_library() -> dict[str, dict[str, dict[str, object]]]:
    """Load the bundled hub season date library."""
    hub_dates_resource = resources.files("epibench").joinpath(
        "hub-dates-library", "hub_dates.json"
    )
    with hub_dates_resource.open("r", encoding="utf-8") as hub_dates_file:
        return json.load(hub_dates_file)


def _parse_season_bounds(
    hub_name: str,
    season_name: str,
    season_bounds: dict[str, object],
) -> tuple[date, date]:
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


def _parse_reference_date_bounds(
    hub_name: str,
    season_name: str,
    season_bounds: dict[str, object],
    season_start: date,
    season_end: date,
) -> tuple[date, date]:
    """Read the hub's actual weekly reference-date window within a July season."""
    reference_dates = season_bounds.get("reference_dates")
    if not isinstance(reference_dates, dict):
        raise ValueError(
            f"Season {season_name!r} for hub {hub_name!r} is missing "
            "`reference_dates` in hub_dates.json."
        )
    try:
        first = datetime.strptime(reference_dates["start"], "%Y-%m-%d").date()
        last = datetime.strptime(reference_dates["end"], "%Y-%m-%d").date()
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"Season {season_name!r} for hub {hub_name!r} has invalid "
            "`reference_dates` in hub_dates.json."
        ) from error
    if not (season_start <= first <= last <= season_end):
        raise ValueError(
            f"Season {season_name!r} for hub {hub_name!r} has reference dates "
            "outside its July 1–June 30 bounds in hub_dates.json."
        )
    return first, last


def _derive_gt_cutoff_dates(
    requested_dates: list[str],
    offset_days: int,
) -> list[str]:
    """
    Derive truth cutoff dates from create/reference dates.

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


def validate_create_dates_against_hub_rounds(
    hub_path: Path,
    requested_dates: list[str],
    gt_cutoff_offset: int,
) -> tuple[list[str], list[str]]:
    """
    Validate create dates against bundled hub season boundaries.

    Rules:
    - all requested dates must be within one July 1–June 30 season
    - known hubs must have dates within that season's reference-date window
    - each requested date must be a 7-day multiple from its first reference date
    - for unknown hubs, only the July-season check is applied

    Returns:
    - validated create dates
    - gt cutoff dates derived from each create date plus ``gt_cutoff_offset``
    """
    requested_date_objects = [
        datetime.strptime(requested_date, "%Y-%m-%d").date()
        for requested_date in requested_dates
    ]
    if len({create_season_start(requested_date) for requested_date in requested_date_objects}) > 1:
        raise ValueError(
            "Requested create dates span multiple July 1–June 30 seasons. "
            "Please limit each create run to one season."
        )

    _warn_on_vintaging_offset_mismatch(
        hub_path=hub_path,
        vintaging_cutoff=gt_cutoff_offset,
    )

    hub_name = _normalize_hub_name(hub_path)
    hub_date_library = load_hub_date_library()

    if hub_name not in hub_date_library:
        logger.warning(
            "Hub %s was not found in bundled hub_dates.json. Proceeding without "
            "validating create dates against the hard-coded season library.",
            hub_name,
        )
        return (
            requested_dates,
            _derive_gt_cutoff_dates(requested_dates, offset_days=gt_cutoff_offset),
        )

    season_matches: list[str] = []
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
            "Requested create dates do not fall within a single season listed in "
            f"hub_dates.json for hub {hub_name!r}."
        )

    if len(season_matches) > 1:
        raise ValueError(
            "Requested create dates match more than one season in hub_dates.json for "
            f"hub {hub_name!r}: {season_matches}. Please limit each create run to one season."
        )

    matched_season_name = season_matches[0]
    matched_season_start, matched_season_end = _parse_season_bounds(
        hub_name=hub_name,
        season_name=matched_season_name,
        season_bounds=hub_date_library[hub_name][matched_season_name],
    )

    first_reference_date, last_reference_date = _parse_reference_date_bounds(
        hub_name=hub_name,
        season_name=matched_season_name,
        season_bounds=hub_date_library[hub_name][matched_season_name],
        season_start=matched_season_start,
        season_end=matched_season_end,
    )
    out_of_range_dates = [
        requested_date.isoformat()
        for requested_date in requested_date_objects
        if not first_reference_date <= requested_date <= last_reference_date
    ]
    if out_of_range_dates:
        raise ValueError(
            f"Create dates outside the reference-date window "
            f"{first_reference_date} through {last_reference_date} for hub "
            f"{hub_name!r}, season {matched_season_name!r}: {out_of_range_dates}"
        )

    invalid_dates = [
        requested_date.strftime("%Y-%m-%d")
        for requested_date in requested_date_objects
        if (requested_date - first_reference_date).days % 7 != 0
    ]
    if invalid_dates:
        raise ValueError(
            "The following create dates are not weekly multiples of the first reference "
            f"date {first_reference_date} for hub {hub_name!r}, season {matched_season_name!r}: "
            f"{invalid_dates}"
        )

    return (
        requested_dates,
        _derive_gt_cutoff_dates(requested_dates, offset_days=gt_cutoff_offset),
    )
