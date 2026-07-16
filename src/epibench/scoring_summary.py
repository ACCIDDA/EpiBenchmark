"""Functions to help write the summary.md file after a scoring run."""

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import pandas as pd

from .horizon_utils import sort_horizon_strings

FILTER_SUMMARY_FILENAME = "summary.md"


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


def build_config_missing_forecast_units_summary(
    submitted_model_dict: Dict[str, pd.DataFrame],
) -> Optional[Dict[str, object]]:
    """Compare submitted models and describe missing forecast units or quantiles."""

    def _normalize_date_strings(date_series: pd.Series) -> pd.Series:
        return pd.to_datetime(date_series, errors="raise").dt.strftime("%Y-%m-%d")

    def _sort_unit(unit: Tuple[str, str, str, str]) -> Tuple[str, str, str, Tuple[int, object]]:
        horizon = str(unit[3])
        horizon_sort = (0, int(horizon)) if horizon.isdigit() else (1, horizon)
        return (unit[0], unit[1], unit[2], horizon_sort)

    def _sort_quantile_level(quantile_level: float) -> float:
        return float(quantile_level)

    per_model_units = {}
    per_model_quantiles = {}
    global_units = set()
    global_quantiles = set()
    global_locations = set()
    global_horizons = set()
    global_reference_dates = set()
    global_target_end_dates = set()

    for model_name, forecast_df in submitted_model_dict.items():
        normalized = forecast_df.copy()
        normalized["reference_date"] = _normalize_date_strings(normalized["reference_date"])
        normalized["target_end_date"] = _normalize_date_strings(normalized["target_end_date"])
        unit_rows = normalized[
            ["reference_date", "target_end_date", "location", "horizon"]
        ].drop_duplicates()
        unit_set = {
            tuple(unit_row)
            for unit_row in unit_rows.itertuples(index=False, name=None)
        }
        quantile_set = {
            round(float(quantile_level), 10)
            for quantile_level in pd.to_numeric(
                normalized["quantile_level"],
                errors="raise",
            )
        }
        per_model_units[model_name] = unit_set
        per_model_quantiles[model_name] = quantile_set
        global_units.update(unit_set)
        global_quantiles.update(quantile_set)
        global_locations.update(unit_rows["location"])
        global_horizons.update(unit_rows["horizon"])
        global_reference_dates.update(unit_rows["reference_date"])
        global_target_end_dates.update(unit_rows["target_end_date"])

    model_summaries = []
    for model_name in sorted(per_model_units):
        missing_units = sorted(global_units - per_model_units[model_name], key=_sort_unit)
        missing_quantiles = sorted(
            global_quantiles - per_model_quantiles[model_name],
            key=_sort_quantile_level,
        )
        if not missing_units and not missing_quantiles:
            continue
        model_summaries.append(
            {
                "model_name": model_name,
                "missing_units": [
                    {
                        "reference_date": missing_unit[0],
                        "target_end_date": missing_unit[1],
                        "location": missing_unit[2],
                        "horizon": missing_unit[3],
                    }
                    for missing_unit in missing_units
                ],
                "missing_quantiles": [
                    f"{missing_quantile:g}"
                    for missing_quantile in missing_quantiles
                ],
            }
        )

    if not model_summaries:
        return None

    return {
        "locations": sorted(str(location) for location in global_locations),
        "horizons": sort_horizon_strings({str(horizon) for horizon in global_horizons}),
        "reference_dates": sorted(str(reference_date) for reference_date in global_reference_dates),
        "target_end_dates": sorted(str(target_end_date) for target_end_date in global_target_end_dates),
        "quantiles": [
            f"{quantile_level:g}"
            for quantile_level in sorted(global_quantiles, key=_sort_quantile_level)
        ],
        "models": model_summaries,
    }


def format_missing_forecast_units_warning(
    missing_forecast_units_summary: Optional[Dict[str, object]],
) -> str:
    """Build a markdown warning block for config runs with uneven units or quantiles."""
    if not missing_forecast_units_summary:
        return ""

    model_summaries = missing_forecast_units_summary.get("models", [])
    if not model_summaries:
        return ""

    lines = [
        "## ⚠️ Warning",
        "",
        "Not all submitted models contain the same forecast units or quantile levels.",
        "",
        "Global submitted-model facets observed across the run:",
        "",
        f"- locations: {', '.join(missing_forecast_units_summary['locations'])}",
        f"- horizons: {', '.join(missing_forecast_units_summary['horizons'])}",
        f"- reference_dates: {', '.join(missing_forecast_units_summary['reference_dates'])}",
        f"- target_end_dates: {', '.join(missing_forecast_units_summary['target_end_dates'])}",
        f"- quantiles: {', '.join(missing_forecast_units_summary['quantiles'])}",
        "",
        "Missing data by model:",
        "",
    ]

    for model_summary in model_summaries:
        lines.extend(
            [
                f"### {model_summary['model_name']}",
                "",
                f"Missing forecast units: {len(model_summary['missing_units'])}",
            ]
        )
        if model_summary["missing_units"]:
            lines.extend(
                [
                    "",
                    "| reference_date | target_end_date | location | horizon |",
                    "| --- | --- | --- | --- |",
                ]
            )
            for missing_unit in model_summary["missing_units"]:
                lines.append(
                    f"| {missing_unit['reference_date']} | "
                    f"{missing_unit['target_end_date']} | "
                    f"{missing_unit['location']} | "
                    f"{missing_unit['horizon']} |"
                )
        lines.extend(
            [
                "",
                "Missing quantiles: "
                + (
                    ", ".join(model_summary["missing_quantiles"])
                    if model_summary["missing_quantiles"]
                    else "None"
                ),
            ]
        )
        lines.append("")

    return "\n".join(lines).rstrip()


def format_excluded_files_summary(
    excluded_files: Iterable[str],
    target: str,
    target_end_dates: Optional[Iterable[str]] = None,
    reference_dates: Optional[Iterable[str]] = None,
    horizons: Optional[Iterable[str]] = None,
    quantiles: Optional[Iterable[float]] = None,
    locations: Optional[Iterable[str]] = None,
    missing_forecast_units_warning: Optional[str] = None,
) -> str:
    """Build a readable text summary of files excluded from scoring."""

    def _format_date_values(date_values: Iterable[str]) -> str:
        """Render date-like values as YYYY-MM-DD strings."""
        return ", ".join(str(date_value).split(" ")[0] for date_value in date_values)

    excluded_file_list = sorted({str(excluded_file) for excluded_file in excluded_files})
    lines = []

    if missing_forecast_units_warning:
        lines.extend([missing_forecast_units_warning, "", "---", ""])

    lines.extend(["file(s) excluded from scoring:", ""])

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
    if horizons is not None:
        lines.extend(
            [
                "",
                f"horizons: {', '.join(str(horizon) for horizon in horizons)}",
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
    horizons: Optional[Iterable[str]] = None,
    quantiles: Optional[Iterable[float]] = None,
    locations: Optional[Iterable[str]] = None,
    missing_forecast_units_warning: Optional[str] = None,
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
            horizons=horizons,
            quantiles=quantiles,
            locations=locations,
            missing_forecast_units_warning=missing_forecast_units_warning,
        ) + "\n",
        encoding="utf-8",
    )
    return output_path
