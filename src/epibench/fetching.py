"""Copy and load challenges bundled with EpiBenchmark."""

from __future__ import annotations

import logging
import shutil
import tempfile
from datetime import date
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Optional

import click
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .challenge import Challenge, Task
from .library import _challenge_resource_directory, load_challenge

logger = logging.getLogger(__name__)

_AGGREGATED_GROUND_TRUTH = "gt.parquet"
_REQUIRED_CHALLENGE_FILES = ("agent.md", "instruction.md", "task_list.csv")


def fetch(challenge_id: str, output_path: Optional[str] = None) -> None:
    """
    Copy one bundled challenge into ``<output_path>/<challenge_id>/``.

    The output path defaults to the current directory. Existing challenge
    directories are never overwritten.
    """
    normalized_challenge_id = Path(challenge_id).stem
    challenge_dir = (
        Path(output_path or ".").expanduser().resolve() / normalized_challenge_id
    )
    _fetch_to_directory(challenge_id, challenge_dir)


def fetch_challenge(challenge_name: str) -> Challenge:
    """Load and return a bundled library challenge for programmatic use.

    The bundled files are copied into temporary storage, and no challenge files
    are retained on the user's machine. The returned challenge contains the
    contents of ``instruction.md``, the library definition's ``notes`` value,
    and its vintaged ground-truth tasks. Tasks follow the order in
    ``task_list.csv``; each task's ``name`` is its reference date and its
    ``gt_df`` is the corresponding ground-truth DataFrame.

    Args:
        challenge_name: name of a challenge in the EpiBenchmark challenge library

    Returns:
        Challenge class instance
    """
    challenge_id = Path(challenge_name).stem
    definition = load_challenge(challenge_name)
    notes = definition.get("notes")
    if not isinstance(notes, str):
        raise ValueError(
            f"Library challenge '{challenge_id}' must define `notes` as a string."
        )

    with tempfile.TemporaryDirectory(prefix="epibench-fetch-") as temporary_dir:
        challenge_dir = Path(temporary_dir) / challenge_id
        _fetch_to_directory(challenge_name, challenge_dir)
        return _load_fetched_challenge(challenge_dir, notes=notes)


def _fetch_to_directory(
    challenge_name: str,
    challenge_dir: Path,
) -> None:
    """Copy a bundled library challenge into an exact destination."""
    challenge_id = Path(challenge_name).stem
    source_dir = _require_challenge_files(challenge_id)
    definition = load_challenge(challenge_name)
    if challenge_dir.exists():
        raise click.ClickException(
            f"'{challenge_dir}' already exists; remove it or pick another --output-path."
        )

    try:
        challenge_dir.mkdir(parents=True)
        _copy_resource_tree(
            source_dir,
            challenge_dir,
            excluded_names={
                _AGGREGATED_GROUND_TRUTH,
                definition["complete_model_scores_file"],
            },
        )
        _split_ground_truth(definition, challenge_id, challenge_dir)
    except BaseException:
        shutil.rmtree(challenge_dir, ignore_errors=True)
        raise

    logger.info("Challenge '%s' returned to %s", challenge_id, challenge_dir)


def _require_challenge_files(challenge_id: str) -> Traversable:
    """Require the files that make a bundled challenge fetchable."""
    source_dir = _challenge_resource_directory(challenge_id)
    required_files = (f"{challenge_id}.json", *_REQUIRED_CHALLENGE_FILES)
    missing_files = [
        name for name in required_files if not source_dir.joinpath(name).is_file()
    ]
    if missing_files:
        raise click.ClickException(
            f"Library challenge '{challenge_id}' is missing required file(s): "
            f"{', '.join(missing_files)}."
        )
    return source_dir


def _copy_resource_tree(
    source_dir: Traversable,
    destination_dir: Path,
    *,
    excluded_names: set[str] | None = None,
) -> None:
    """Recursively copy a package-resource directory to the filesystem."""
    excluded_names = excluded_names or set()
    for resource in source_dir.iterdir():
        if resource.name.startswith(".") or resource.name in excluded_names:
            continue
        destination = destination_dir / resource.name
        if resource.is_dir():
            destination.mkdir()
            _copy_resource_tree(resource, destination)
        elif resource.is_file():
            with (
                resource.open("rb") as source_file,
                destination.open("wb") as output_file,
            ):
                shutil.copyfileobj(source_file, output_file)


def _split_ground_truth(
    definition: dict,
    challenge_id: str,
    challenge_dir: Path,
) -> None:
    """Expand bundled ground truth using the challenge's required task list."""
    task_list = _read_task_list(_task_list_path(challenge_dir))
    reference_dates = definition["reference_dates"]
    listed_dates = task_list["date"].tolist()
    if len(listed_dates) != len(set(listed_dates)) or set(listed_dates) != set(reference_dates):
        raise ValueError("Task list dates do not match challenge reference dates.")

    task_sources: dict[str, pa.Table] = {}
    for source_id in definition.get("sub_challenges") or [challenge_id]:
        _require_challenge_files(source_id)
        source_definition = load_challenge(source_id)
        source_resource = _challenge_resource_directory(source_id).joinpath(
            _AGGREGATED_GROUND_TRUTH
        )
        with source_resource.open("rb") as source_file:
            source_gt = pq.read_table(source_file)
        for reference_date in source_definition["reference_dates"]:
            if reference_date in task_sources:
                raise ValueError(f"Source challenges overlap on {reference_date}.")
            task_sources[reference_date] = source_gt

    if set(reference_dates) != set(task_sources):
        raise ValueError("Challenge reference dates do not match ground-truth sources.")

    for task in task_list.itertuples(index=False):
        reference_date = str(task.date).strip()
        _write_ground_truth_task(
            task_sources[reference_date],
            reference_date,
            challenge_dir / str(task.path_to_gt).strip(),
        )


def _write_ground_truth_task(
    ground_truth: pa.Table, reference_date: str, output_path: Path
) -> None:
    """Write one reference date in the standard fetched task layout."""
    reference_value = pa.scalar(date.fromisoformat(reference_date), type=pa.date32())
    dated_ground_truth = ground_truth.filter(
        pc.equal(ground_truth["reference_date"], reference_value)
    ).drop(["reference_date"])
    if dated_ground_truth.num_rows == 0:
        raise ValueError(f"No ground truth found for {reference_date}.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        dated_ground_truth,
        output_path,
        compression="brotli",
        compression_level=5,
        use_dictionary=["location", "target"],
        write_statistics=True,
    )


def _task_list_path(challenge_dir: Path) -> Path:
    """Return the fetched CSV task-list path."""
    return challenge_dir / "task_list.csv"


def _read_task_list(task_list_path: Path) -> pd.DataFrame:
    """Read a fetched task list while preserving its path and date strings."""
    return pd.read_csv(
        task_list_path,
        dtype={"date": str, "path_to_gt": str},
        keep_default_na=False,
    )


def _load_fetched_challenge(challenge_dir: Path, *, notes: str) -> Challenge:
    """Load the programmatic challenge object from an unpacked challenge folder."""
    instructions_path = challenge_dir / "instruction.md"
    if not instructions_path.is_file():
        raise FileNotFoundError(
            f"Fetched challenge is missing its instructions: {instructions_path}."
        )
    return Challenge(
        instructions=instructions_path.read_text(encoding="utf-8"),
        tasks=_load_ground_truth_tasks(challenge_dir),
        notes=notes,
    )


def _load_ground_truth_tasks(challenge_dir: Path) -> list[Task]:
    """Load the ground-truth files referenced by a fetched task list."""
    task_list_path = _task_list_path(challenge_dir)
    if not task_list_path.is_file():
        raise FileNotFoundError(
            f"Fetched challenge is missing its task list: {task_list_path}."
        )

    task_list = _read_task_list(task_list_path)
    required_columns = {"date", "path_to_gt"}
    missing_columns = required_columns.difference(task_list.columns)
    if missing_columns:
        raise ValueError(
            "Fetched task_list.csv is missing required column(s): "
            f"{', '.join(sorted(missing_columns))}."
        )
    if task_list.empty:
        raise ValueError(
            "Fetched task_list.csv does not contain any ground-truth entries."
        )
    if (task_list["date"].str.strip() == "").any():
        raise ValueError(
            "Fetched task_list.csv contains an empty reference date."
        )
    if (task_list["path_to_gt"].str.strip() == "").any():
        raise ValueError(
            "Fetched task_list.csv contains an empty ground-truth path."
        )

    duplicate_dates = task_list.loc[task_list["date"].duplicated(), "date"].tolist()
    if duplicate_dates:
        raise ValueError(
            "Fetched task_list.csv contains duplicate reference date(s): "
            f"{', '.join(duplicate_dates)}."
        )

    challenge_root = challenge_dir.resolve()
    tasks: list[Task] = []
    for task in task_list.itertuples(index=False):
        reference_date = task.date.strip()
        relative_path = Path(task.path_to_gt.strip())
        if relative_path.is_absolute():
            raise ValueError(
                f"Ground-truth path for {reference_date} must be relative to the challenge folder."
            )

        ground_truth_path = (challenge_root / relative_path).resolve()
        try:
            ground_truth_path.relative_to(challenge_root)
        except ValueError as error:
            raise ValueError(
                f"Ground-truth path for {reference_date} resolves outside the challenge folder."
            ) from error

        suffix = ground_truth_path.suffix.lower()
        if suffix not in {".csv", ".parquet"}:
            raise ValueError(
                f"Ground-truth file for {reference_date} must be a CSV or Parquet file: "
                f"{relative_path}."
            )
        if not ground_truth_path.is_file():
            raise FileNotFoundError(
                f"Could not find ground-truth file for {reference_date}: {ground_truth_path}."
            )

        if suffix == ".parquet":
            ground_truth = pd.read_parquet(ground_truth_path)
            if "target_end_date" in ground_truth:
                ground_truth["target_end_date"] = ground_truth[
                    "target_end_date"
                ].astype(str)
            if "location" in ground_truth:
                ground_truth["location"] = ground_truth["location"].astype(str)
            if "observed" in ground_truth:
                ground_truth["observed"] = ground_truth["observed"].astype(float)
        else:
            ground_truth = pd.read_csv(
                ground_truth_path,
                dtype={"location": str},
                low_memory=False,
            )
        tasks.append(Task(name=reference_date, gt_df=ground_truth))

    return tasks
