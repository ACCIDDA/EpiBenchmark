"""Public Python API and shared implementation for EpiBenchmark create command."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Literal

import pandas as pd

from .challenge import Challenge, Task, _save_tasks
from .config import Config, CreateParameters, build_create_parameters
from .create_ground_truth import gt_from_hub

logger = logging.getLogger(__name__)


def create(
    *,
    hub_path: str | Path,
    target: str,
    dates: dict[str, str] | list[str],
    ground_truth_file: str,
    observed_column_name: str,
    location_column_name: str,
    date_column_name: str,
    vintaging: bool,
    vintaging_method: Literal["as_of", "checkout"] | None = None,
    vintaging_offset: int | None = None,
) -> Challenge:
    """Create vintaged ground-truth tasks (refrence dates) from explicit inputs.

    Results remain in memory until :meth:`Challenge.save` is called. The
    ``dates`` argument accepts either a list of ``YYYY-MM-DD`` strings or a
    dictionary with ``start_date``, ``end_date``, and weekly ``freq`` entries.
    ``vintaging_method`` and ``vintaging_offset`` are required when
    ``vintaging`` is true.
    """
    logger.info("Validating create inputs...")
    parameters = build_create_parameters(
        hub_path=hub_path,
        target=target,
        dates=dates,
        ground_truth_file=ground_truth_file,
        observed_column_name=observed_column_name,
        location_column_name=location_column_name,
        date_column_name=date_column_name,
        vintaging=vintaging,
        vintaging_method=vintaging_method,
        vintaging_offset=vintaging_offset,
    )
    return _create_challenge(parameters)


def _create_challenge(parameters: CreateParameters) -> Challenge:
    """Create in-memory tasks from validated, normalized parameters."""
    logger.info("Fetching ground-truth data from hub...")
    ground_truth_by_date = gt_from_hub(
        hub_path=parameters.hub_path,
        target=parameters.target,
        reference_dates=parameters.dates,
        gt_file=parameters.ground_truth_file,
        observed_column=parameters.observed_column_name,
        location_column=parameters.location_column_name,
        date_column=parameters.date_column_name,
        data_cutoff_dates=parameters.gt_cutoff_dates,
        vintaging=parameters.vintaging,
        vintaging_method=parameters.vintaging_method,
    )

    tasks: list[Task] = []
    for reference_date, ground_truth in ground_truth_by_date.items():
        if isinstance(ground_truth, pd.DataFrame):
            tasks.append(Task(name=reference_date, gt_df=ground_truth))
        else:
            logger.warning(
                "NOTICE: No ground truth data found for target %r for date %s.",
                parameters.target,
                reference_date,
            )

    return Challenge(instructions=None, tasks=tasks)


def _create_from_config(config_path: str) -> None:
    """Run the persistent, YAML-configured create workflow used by the CLI."""
    logger.info("Validating config...")
    config = Config(config_path=config_path, pipeline="create")
    challenge = _create_challenge(config.create_parameters)
    challenge_id = _build_challenge_id(
        challenge_name=config.challenge_name,
        parameters=config.create_parameters,
    )
    output_base = config.output_path / challenge_id
    try:
        output_base.mkdir(parents=True, exist_ok=False)
    except FileExistsError as error:
        raise FileExistsError(
            f"There is already a folder with challenge_id {challenge_id} "
            f"at output directory {config.output_path}"
        ) from error

    _save_tasks(
        challenge.tasks,
        output_dir=output_base,
        include_task_list=True,
    )


def _build_challenge_id(
    *,
    challenge_name: str,
    parameters: CreateParameters,
) -> str:
    """Construct the CLI's deterministic challenge identifier."""
    hub_name = parameters.hub_path.name
    admin_json_path = parameters.hub_path / "hub-config" / "admin.json"
    if admin_json_path.is_file():
        try:
            with admin_json_path.open("r", encoding="utf-8") as admin_file:
                admin_data = json.load(admin_file)
            repository_name = admin_data.get("repository", {}).get("name")
            if isinstance(repository_name, str) and repository_name.strip():
                hub_name = repository_name
        except (json.JSONDecodeError, OSError) as error:
            logger.warning(
                "Unable to read %s (%s). Using folder name '%s'.",
                admin_json_path,
                error,
                hub_name,
            )

    hash_input = {
        "hub_name": hub_name,
        "target": parameters.target,
        "ground_truth_file": parameters.ground_truth_file,
        "observed_column_name": parameters.observed_column_name,
        "location_column_name": parameters.location_column_name,
        "date_column_name": parameters.date_column_name,
        "dates": parameters.dates,
        "vintaging": parameters.vintaging,
        "vintaging_method": parameters.vintaging_method,
        "vintaging_offset": parameters.vintaging_offset,
    }
    hash_string = json.dumps(hash_input, sort_keys=True)
    short_hash = hashlib.sha256(hash_string.encode("utf-8")).hexdigest()[:10]
    return f"{challenge_name}_{short_hash}"
