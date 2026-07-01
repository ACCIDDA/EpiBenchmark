"""Helpers for hub schedule metadata and setup-date validation."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def load_hub_round_definitions(hub_path: Path) -> list[dict] | None:
    """
    Load round definitions from hub-config/tasks.json.

    Supports hubs that key forecast dates by either `reference_date`
    or `origin_date`. Origin_date is a patch for Hopkins IDD RSV-forecast-hub.
    """
    tasks_path = hub_path / "hub-config" / "tasks.json"
    if not tasks_path.is_file():
        logger.warning(
            "Could not find hub schedule metadata at %s. "
            "Proceeding without validating setup dates against the hub; "
            "requested dates may not match official hub reference dates.",
            tasks_path,
        )
        return None

    with open(tasks_path, "r", encoding="utf-8") as tasks_file:
        tasks_config = json.load(tasks_file)

    round_definitions = []
    for round_index, round_config in enumerate(tasks_config.get("rounds", []), start=1):
        reference_dates = set()
        targets = set()
        date_task_name = None
        for model_task in round_config.get("model_tasks", []):
            task_ids = model_task.get("task_ids", {})

            if date_task_name is None:
                if "reference_date" in task_ids:
                    date_task_name = "reference_date"
                elif "origin_date" in task_ids:
                    date_task_name = "origin_date"

            reference_date_task = task_ids.get(date_task_name, {}) if date_task_name else {}
            for field in ("required", "optional"):
                values = reference_date_task.get(field)
                if isinstance(values, list):
                    reference_dates.update(str(value) for value in values)

            target_task = task_ids.get("target", {})
            for field in ("required", "optional"):
                values = target_task.get(field)
                if isinstance(values, list):
                    targets.update(str(value) for value in values)

        submissions_due = round_config.get("submissions_due", {})
        round_label = (
            round_config.get("round_name")
            or round_config.get("name")
            or f"round_{round_index}"
        )

        round_definitions.append({
            "round_label": str(round_label),
            "date_task_name": date_task_name,
            "reference_dates": sorted(reference_dates),
            "targets": sorted(targets),
            "submission_cutoff_days": (
                submissions_due.get("end")
                if date_task_name is not None
                and submissions_due.get("relative_to") == date_task_name
                and isinstance(submissions_due.get("end"), int)
                else None
            ),
        })

    if not round_definitions:
        raise ValueError(
            f"No rounds were found in hub schedule metadata at {tasks_path}."
        )

    return round_definitions


def validate_setup_dates_against_hub_rounds(
    hub_path: Path,
    requested_dates: list[str],
    targets: list[str],
) -> tuple[list[str], list[str], str | None]:
    """
    Validate setup reference dates against tasks.json and derive gt cutoff dates.

    Rules:
    - every requested date must be an official forecast-date value in tasks.json
    - all requested dates must belong to exactly one hub round/season
    """
    round_definitions = load_hub_round_definitions(hub_path)
    if round_definitions is None:
        return requested_dates, list(requested_dates), None

    date_to_rounds = {}
    for round_index, round_definition in enumerate(round_definitions):
        for reference_date in round_definition["reference_dates"]:
            date_to_rounds.setdefault(reference_date, []).append(round_index)

    invalid_dates = [date for date in requested_dates if date not in date_to_rounds]
    if invalid_dates:
        raise ValueError(
            "The following setup dates are not valid hub forecast-date values from "
            f"hub-config/tasks.json: {invalid_dates}"
        )

    selected_round_indexes = set()
    for date in requested_dates:
        matching_rounds = date_to_rounds[date]
        if len(matching_rounds) != 1:
            raise ValueError(
                f"Reference date {date} matched {len(matching_rounds)} rounds in tasks.json. "
                "Setup requires each requested date to map to exactly one round."
            )
        selected_round_indexes.add(matching_rounds[0])

    if len(selected_round_indexes) != 1:
        selected_round_labels = [
            round_definitions[index]["round_label"]
            for index in sorted(selected_round_indexes)
        ]
        raise ValueError(
            "Requested setup dates span more than one hub round/season: "
            f"{selected_round_labels}. Please limit each setup run to one season."
        )

    selected_round = round_definitions[selected_round_indexes.pop()]
    allowed_targets = set(selected_round["targets"])
    if allowed_targets and not set(targets).issubset(allowed_targets):
        invalid_targets = sorted(set(targets) - allowed_targets)
        raise ValueError(
            "The following targets are not allowed by the selected hub round in "
            f"tasks.json: {invalid_targets}"
        )

    submission_cutoff_days = selected_round["submission_cutoff_days"]
    if submission_cutoff_days is None:
        cutoff_dates = list(requested_dates)
    else:
        cutoff_dates = [
            (
                datetime.strptime(reference_date, "%Y-%m-%d")
                + timedelta(days=submission_cutoff_days)
            ).strftime("%Y-%m-%d")
            for reference_date in requested_dates
        ]

    return requested_dates, cutoff_dates, selected_round["round_label"]
