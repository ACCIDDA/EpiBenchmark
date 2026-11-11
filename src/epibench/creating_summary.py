"""Non-fatal coverage diagnostics for created ground-truth tasks."""

from datetime import date

import pandas as pd

from .challenge import Task
from .config import CreateParameters
from .hub_date_utils import create_season_start


def _cell(value: object) -> str:
    return (
        str(value).replace("&", "&amp;").replace("<", "&lt;")
        .replace("|", "&#124;").replace("\n", " ").replace("\r", " ")
    )


def format_create_summary(tasks: list[Task], parameters: CreateParameters) -> str:
    """Report absent rows and missing observed values without changing tasks."""
    cutoffs = dict(zip(parameters.dates, parameters.gt_cutoff_dates))
    sections = []
    has_missing = False
    checked_locations: set[object] = set()
    checked_combinations = 0
    for task in tasks:
        reference_day = date.fromisoformat(task.name)
        start = create_season_start(reference_day).isoformat()
        end = min(task.name, cutoffs[task.name])
        coverage = task.gt_df.attrs["create_coverage"]
        expected_dates = [day for day in coverage["dates"] if start <= day <= end]
        expected_locations = sorted(coverage["locations"], key=str)
        checked_locations.update(expected_locations)
        checked_combinations += len(expected_dates) * len(expected_locations)
        data = task.gt_df
        days = pd.to_datetime(data["target_end_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        present = set(zip(days, data["location"]))
        valid = data["observed"].notna()
        observed = set(zip(days[valid], data.loc[valid, "location"]))
        missing = [
            (day, location, "No row" if (day, location) not in present else "Missing observed value")
            for day in expected_dates for location in expected_locations
            if (day, location) not in observed
        ]
        sections.extend([
            f"### Reference date {task.name}", "",
            f"Data cutoff: {cutoffs[task.name]}. Missing combinations: {len(missing)}.", "",
        ])
        if missing:
            has_missing = True
            sections.extend([
                "| Target end date | Location | Reason |",
                "| --- | --- | --- |",
                *[f"| {day} | {_cell(location)} | {reason} |" for day, location, reason in missing],
                "",
            ])
        else:
            sections.extend(["No missing combinations in the checked source grid.", ""])
    reference_dates = sorted(task.name for task in tasks)
    location_description = ", ".join(
        _cell(location) for location in sorted(checked_locations, key=str)
    )
    lines = [
        "# Create summary", "",
        f"- Target: {_cell(parameters.target)}",
        f"- Source: {_cell(parameters.ground_truth_file)}",
        f"- Reference dates: {', '.join(reference_dates)}",
        f"- Locations: {location_description}",
        f"- Checked: {checked_combinations} date–location combinations", "",
    ]
    if has_missing:
        lines.extend(sections)
    else:
        lines.extend(["No missing combinations found.", ""])
    return "\n".join(lines)
