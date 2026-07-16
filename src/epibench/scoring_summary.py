"""Helpers for writing concise scoring summaries."""

from pathlib import Path
from typing import Dict, Iterable, Optional, Set

FILTER_SUMMARY_FILENAME = "summary.txt"


def record_filtered_facets(
    filtered_facets_by_file: Optional[Dict[str, Set[str]]],
    input_file: str,
    facets: Iterable[str],
) -> None:
    """Record one or more filtered facet names for a given input file."""
    if filtered_facets_by_file is None:
        return

    facet_set = filtered_facets_by_file.setdefault(input_file, set())
    facet_set.update(str(facet) for facet in facets)


def format_excluded_files_summary(
    excluded_files: Iterable[str],
    target: str,
    target_end_dates: Optional[Iterable[str]] = None,
    reference_dates: Optional[Iterable[str]] = None,
    quantiles: Optional[Iterable[float]] = None,
    locations: Optional[Iterable[str]] = None,
) -> str:
    """Build a readable text summary of files excluded from scoring."""

    def _format_date_values(date_values: Iterable[str]) -> str:
        """Render date-like values as YYYY-MM-DD strings."""
        return ", ".join(str(date_value).split(" ")[0] for date_value in date_values)

    excluded_file_list = sorted({str(excluded_file) for excluded_file in excluded_files})
    lines = ["file(s) excluded from scoring:", ""]

    if not excluded_file_list:
        lines.append("None")
        return "\n".join(lines)

    lines.extend(f"- {excluded_file}" for excluded_file in excluded_file_list)

    lines.extend(
        [
            "",
            "because they contained zero lines of one or more of the following value sets",
            "",
            f"target: {target}",
        ]
    )
    if target_end_dates is not None:
        lines.extend(
            [
                "",
                f"target_end_date: {_format_date_values(target_end_dates)}",
            ]
        )
    if reference_dates is not None:
        lines.extend(
            [
                "",
                f"reference_dates: {_format_date_values(reference_dates)}",
            ]
        )
    if quantiles is not None:
        lines.extend(
            [
                "",
                f"quantiles: {', '.join(str(quantile) for quantile in quantiles)}",
            ]
        )
    if locations is not None:
        lines.extend(
            [
                "",
                f"locations: {', '.join(str(location) for location in locations)}",
            ]
        )
    lines.extend(
        [
            "",
            "output_type: quantile",
        ]
    )
    return "\n".join(lines)


def write_excluded_files_summary(
    excluded_files: Iterable[str],
    target: str,
    output_dir: Path,
    target_end_dates: Optional[Iterable[str]] = None,
    reference_dates: Optional[Iterable[str]] = None,
    quantiles: Optional[Iterable[float]] = None,
    locations: Optional[Iterable[str]] = None,
    filename: str = FILTER_SUMMARY_FILENAME,
) -> Path:
    """Write the excluded-files summary text file and return its path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    if output_path.exists():
        raise FileExistsError(
            "Scoring summary output file already exists and will not be overwritten: "
            f"{output_path}"
        )

    output_path.write_text(
        format_excluded_files_summary(
            excluded_files=excluded_files,
            target=target,
            target_end_dates=target_end_dates,
            reference_dates=reference_dates,
            quantiles=quantiles,
            locations=locations,
        ) + "\n",
        encoding="utf-8",
    )
    return output_path
