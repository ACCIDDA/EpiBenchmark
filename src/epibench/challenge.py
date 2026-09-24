"""Shared in-memory representation of an EpiBenchmark challenge."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class Task:
    """Ground truth for one challenge reference date."""

    name: str
    gt_df: pd.DataFrame


@dataclass
class Challenge:
    """
    Metadata and ground-truth tasks for a fetched or created challenge.

    ``instructions`` and ``notes`` are populated for library challenges and are
    ``None`` for challenges created directly from hub ground truth (i.e., the
    "config style" route).
    """

    instructions: str | None
    tasks: list[Task]
    notes: str | None = None

    def save(self, output_path: str | Path | None = None) -> None:
        """Save every ground-truth task beneath ``<output_path>/gt/``.

        The destination defaults to the current working directory. Existing
        ``gt`` paths are never overwritten.
        """
        output_dir = Path(output_path or Path.cwd()).expanduser().resolve()
        _save_tasks(self.tasks, output_dir=output_dir, include_task_list=False)
        logger.info("Ground-truth tasks saved to %s", output_dir / "gt")


def _validate_tasks_for_saving(
    tasks: list[Task],
) -> list[Task]:
    """Validate mutable challenge tasks before creating any output files."""
    if not isinstance(tasks, list):
        raise TypeError("Challenge tasks must be a list.")
    if not tasks:
        raise ValueError("Challenge does not contain any ground-truth tasks to save.")

    tasks_to_save: list[Task] = []
    seen_dates: set[str] = set()
    for task_number, task in enumerate(tasks, start=1):
        if not isinstance(task, Task):
            raise TypeError(
                f"Challenge task {task_number} must be a Task instance."
            )

        reference_date = task.name
        ground_truth = task.gt_df
        if not isinstance(reference_date, str):
            raise TypeError(f"Challenge task {task_number}'s name must be a string.")
        try:
            parsed_date = date.fromisoformat(reference_date)
        except ValueError as error:
            raise ValueError(
                f"Challenge task {task_number} has an invalid date: {reference_date!r}. "
                "Dates must use YYYY-MM-DD format."
            ) from error
        if parsed_date.isoformat() != reference_date:
            raise ValueError(
                f"Challenge task {task_number} has an invalid date: {reference_date!r}. "
                "Dates must use YYYY-MM-DD format."
            )
        if reference_date in seen_dates:
            raise ValueError(f"Challenge tasks contain duplicate date {reference_date!r}.")
        if not isinstance(ground_truth, pd.DataFrame):
            raise TypeError(
                f"Challenge task {reference_date!r} must contain a pandas DataFrame."
            )

        seen_dates.add(reference_date)
        tasks_to_save.append(task)

    return tasks_to_save


def _save_tasks(
    tasks: list[Task],
    *,
    output_dir: Path,
    include_task_list: bool,
) -> None:
    """Save task CSVs, optionally including the create-CLI task list."""
    tasks_to_save = _validate_tasks_for_saving(tasks)
    gt_dir = output_dir / "gt"
    task_list_path = output_dir / "task_list.csv"
    relevant_paths = [gt_dir]
    if include_task_list:
        relevant_paths.append(task_list_path)
    conflicts = [path for path in relevant_paths if path.exists()]
    if conflicts:
        formatted_conflicts = ", ".join(str(path) for path in conflicts)
        raise FileExistsError(
            "The following challenge output path(s) already exist and will not be "
            f"overwritten: {formatted_conflicts}."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    gt_dir.mkdir()
    try:
        task_rows: list[dict[str, str]] = []
        for task in tasks_to_save:
            reference_date = task.name
            date_dir = gt_dir / reference_date
            date_dir.mkdir()
            filename = f"{reference_date.replace('-', '')}_gt.csv"
            ground_truth_path = date_dir / filename
            task.gt_df.to_csv(ground_truth_path, index=False)
            task_rows.append(
                {
                    "date": reference_date,
                    "path_to_gt": str(ground_truth_path.relative_to(output_dir)),
                }
            )

        if include_task_list:
            pd.DataFrame(task_rows, columns=["date", "path_to_gt"]).to_csv(
                task_list_path,
                index=False,
            )
    except BaseException:
        shutil.rmtree(gt_dir, ignore_errors=True)
        if include_task_list:
            task_list_path.unlink(missing_ok=True)
        raise
