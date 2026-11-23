"""Non-fatal coverage diagnostics for created ground-truth tasks."""

from collections.abc import Mapping

import polars as pl

from .challenge import Task
from .config import CreateParameters
from .create_ground_truth import CoverageExpectations


def _cell(value: object) -> str:
    return (
        str(value).replace("&", "&amp;").replace("<", "&lt;")
        .replace("|", "&#124;").replace("\n", " ").replace("\r", " ")
    )


def format_create_summary(
    tasks: list[Task],
    parameters: CreateParameters,
    coverage_by_date: Mapping[str, CoverageExpectations],
) -> str:
    """Report absent rows and missing observed values without changing tasks."""
    cutoffs = dict(zip(parameters.dates, parameters.gt_cutoff_dates))
    sections = []
    has_missing = False
    checked_locations: set[object] = set()
    checked_combinations = 0
    for task in tasks:
        end = cutoffs[task.name]
        coverage = coverage_by_date[task.name]
        expected_dates = [day for day in coverage.dates if day <= end]
        expected_locations = sorted(coverage.locations, key=str)
        checked_locations.update(expected_locations)
        checked_combinations += len(expected_dates) * len(expected_locations)
        rows = task.gt_df.select(
            pl.col("target_end_date").dt.to_string("%Y-%m-%d"), "location", "observed"
        )
        present = set()
        observed = set()
        for day, location, value in rows.iter_rows():
            present.add((day, location))
            if value is not None:
                observed.add((day, location))
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
