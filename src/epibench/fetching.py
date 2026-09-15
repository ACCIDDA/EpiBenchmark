"""Download and load EpiBenchmark challenge data from Zenodo."""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
import zipfile
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen

import click
import pandas as pd

from .library import is_published, load_challenge

logger = logging.getLogger(__name__)

_ZENODO_RECORDS_API = "https://zenodo.org/api/records"


@dataclass
class Challenge:
    """A fetched challenge's human-readable instructions and ground-truth tasks."""

    instructions: str
    tasks: list[dict[str, pd.DataFrame]]

    def save(self, output_path: str | Path | None = None) -> "Challenge":
        """Method to save every ground-truth task .CSV beneath ``<output_path>/gt/<reference_date>/``.

        The destination defaults to the current working directory. Existing
        ``gt`` paths are never overwritten.
        """
        tasks_to_save = _validate_tasks_for_saving(self.tasks)
        output_dir = Path(output_path or Path.cwd()).expanduser().resolve()
        gt_dir = output_dir / "gt"
        if gt_dir.exists():
            raise FileExistsError(
                f"'{gt_dir}' already exists; remove it or choose another output_path."
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        gt_dir.mkdir()
        try:
            for reference_date, ground_truth in tasks_to_save:
                date_dir = gt_dir / reference_date
                date_dir.mkdir()
                filename = f"{reference_date.replace('-', '')}_gt.csv"
                ground_truth.to_csv(date_dir / filename, index=False)
        except BaseException:
            shutil.rmtree(gt_dir, ignore_errors=True)
            raise

        logger.info("Ground-truth tasks saved to %s", gt_dir)
        return self


def _validate_tasks_for_saving(
    tasks: list[dict[str, pd.DataFrame]],
) -> list[tuple[str, pd.DataFrame]]:
    """Validate mutable challenge tasks before creating any output files."""
    if not isinstance(tasks, list):
        raise TypeError("Challenge tasks must be a list.")
    if not tasks:
        raise ValueError("Challenge does not contain any ground-truth tasks to save.")

    tasks_to_save: list[tuple[str, pd.DataFrame]] = []
    seen_dates: set[str] = set()
    for task_number, task in enumerate(tasks, start=1):
        if not isinstance(task, dict) or len(task) != 1:
            raise ValueError(
                f"Challenge task {task_number} must be a dictionary containing exactly one date."
            )

        reference_date, ground_truth = next(iter(task.items()))
        if not isinstance(reference_date, str):
            raise TypeError(f"Challenge task {task_number}'s date must be a string.")
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
        tasks_to_save.append((reference_date, ground_truth))

    return tasks_to_save


def fetch(challenge_id: str, output_path: Optional[str] = None) -> None:
    """
    Download one library challenge's data files from Zenodo into
    ``<output_path>/<challenge_id>/`` (defaults to the current directory),
    unzipping any archives and keeping a copy of the challenge definition.
    """
    normalized_challenge_id = Path(challenge_id).stem
    challenge_dir = Path(output_path or ".").expanduser().resolve() / normalized_challenge_id
    _fetch_to_directory(challenge_id, challenge_dir, show_progress=True)


def fetch_challenge(challenge_name: str) -> Challenge:
    """Download and return a library challenge for programmatic use.

    The challenge is downloaded into temporary storage, and no challenge files
    are retained on the user's machine. The returned challenge contains the
    contents of ``instructions.md`` and its vintaged ground-truth tasks. Tasks
    follow the order in ``task_list.csv``; each item maps one reference date to
    its ground-truth DataFrame.

    Args:
        challenge_name: name of a published challenge in the EpiBenchmark challenge library

    Returns:
        Challenge class instance
    """
    challenge_id = Path(challenge_name).stem
    with tempfile.TemporaryDirectory(prefix="epibench-fetch-") as temporary_dir:
        challenge_dir = Path(temporary_dir) / challenge_id
        _fetch_to_directory(challenge_name, challenge_dir, show_progress=False)
        return _load_fetched_challenge(challenge_dir)


def _fetch_to_directory(
    challenge_name: str,
    challenge_dir: Path,
    *,
    show_progress: bool,
) -> None:
    """Download and unpack a library challenge into an exact destination."""
    definition = load_challenge(challenge_name)
    challenge_id = Path(challenge_name).stem
    if not is_published(definition):
        raise click.ClickException(
            f"Challenge '{challenge_id}' has not been published to Zenodo yet "
            f"(zenodo_doi is '{definition.get('zenodo_doi')}')."
        )

    # Assumes a zenodo doi looks like '10.5281/zenodo.1234567'; with the record id as the trailing number.
    record_id = str(definition["zenodo_doi"]).rsplit("zenodo.", 1)[-1].strip("/")
    if challenge_dir.exists():
        raise click.ClickException(
            f"'{challenge_dir}' already exists; remove it or pick another --output-path."
        )
    challenge_dir.mkdir(parents=True)

    try:
        files = _get_json(f"{_ZENODO_RECORDS_API}/{record_id}").get("files") or []
        if not files:
            raise click.ClickException(f"Zenodo record {record_id} contains no files.")
        logger.info("Downloading %d file(s) from Zenodo record %s...", len(files), record_id)
        for file_info in files:
            _download(file_info, challenge_dir, show_progress=show_progress)
        for archive in challenge_dir.glob("*.zip"):
            _extract_zip(archive, challenge_dir)
            archive.unlink()
        # keep the challenge definition alongside the data for downstream scoring
        (challenge_dir / f"{challenge_id}.json").write_text(json.dumps(definition, indent=4))
    except BaseException:
        shutil.rmtree(challenge_dir, ignore_errors=True)  # don't leave a partial folder behind
        raise

    logger.info("Challenge '%s' downloaded to %s ✅", challenge_id, challenge_dir)


def _load_fetched_challenge(challenge_dir: Path) -> Challenge:
    """Load the programmatic challenge object from an unpacked challenge folder."""
    instructions_path = challenge_dir / "instructions.md"
    if not instructions_path.is_file():
        raise FileNotFoundError(
            f"Fetched challenge is missing its instructions: {instructions_path}."
        )

    return Challenge(
        instructions=instructions_path.read_text(encoding="utf-8"),
        tasks=_load_ground_truth_data(challenge_dir),
    )


def _load_ground_truth_data(challenge_dir: Path) -> list[dict[str, pd.DataFrame]]:
    """Load the ground-truth files referenced by a fetched task list."""
    task_list_path = challenge_dir / "task_list.csv"
    if not task_list_path.is_file():
        raise FileNotFoundError(
            f"Fetched challenge is missing its task list: {task_list_path}."
        )

    task_list = pd.read_csv(
        task_list_path,
        dtype={"date": str, "path_to_gt": str},
        keep_default_na=False,
    )
    required_columns = {"date", "path_to_gt"}
    missing_columns = required_columns.difference(task_list.columns)
    if missing_columns:
        raise ValueError(
            "Fetched task_list.csv is missing required column(s): "
            f"{', '.join(sorted(missing_columns))}."
        )
    if task_list.empty:
        raise ValueError("Fetched task_list.csv does not contain any ground-truth entries.")
    if (task_list["date"].str.strip() == "").any():
        raise ValueError("Fetched task_list.csv contains an empty reference date.")
    if (task_list["path_to_gt"].str.strip() == "").any():
        raise ValueError("Fetched task_list.csv contains an empty ground-truth path.")

    duplicate_dates = task_list.loc[task_list["date"].duplicated(), "date"].tolist()
    if duplicate_dates:
        raise ValueError(
            "Fetched task_list.csv contains duplicate reference date(s): "
            f"{', '.join(duplicate_dates)}."
        )

    challenge_root = challenge_dir.resolve()
    ground_truth_data: list[dict[str, pd.DataFrame]] = []
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

        if ground_truth_path.suffix.lower() != ".csv":
            raise ValueError(
                f"Ground-truth file for {reference_date} must be a CSV: {relative_path}."
            )
        if not ground_truth_path.is_file():
            raise FileNotFoundError(
                f"Could not find ground-truth file for {reference_date}: {ground_truth_path}."
            )

        ground_truth = pd.read_csv(
            ground_truth_path,
            dtype={"location": str},
            low_memory=False,
        )
        ground_truth_data.append({reference_date: ground_truth})

    return ground_truth_data


def _get_json(url: str) -> dict:
    """GET a URL and parse the JSON body, turning network errors into ClickExceptions."""
    try:
        with urlopen(Request(url, headers={"Accept": "application/json"})) as response:
            return json.load(response)
    except OSError as error:  # HTTPError/URLError are OSError subclasses
        raise click.ClickException(f"Could not reach Zenodo ({url}): {error}") from error


def _download(file_info: dict, dest_dir: Path, *, show_progress: bool = True) -> None:
    """Download one Zenodo file entry into ``dest_dir``."""
    name, size, url = file_info["key"], file_info["size"], file_info["links"]["self"]
    request = Request(url, headers={"Accept": "*/*", "User-Agent": "epibench"})
    try:
        with urlopen(request) as response, (dest_dir / name).open("wb") as out_file:
            progress = (
                click.progressbar(length=size, label=f"  {name}", show_pos=True)
                if show_progress
                else nullcontext()
            )
            with progress as bar:
                for chunk in iter(lambda: response.read(1 << 16), b""):
                    out_file.write(chunk)
                    if bar is not None:
                        bar.update(len(chunk))
    except OSError as error:
        raise click.ClickException(f"Failed to download '{name}' from Zenodo: {error}") from error


def _extract_zip(archive_path: Path, dest_dir: Path) -> None:
    """Unzip into ``dest_dir``, stripping a single wrapping top-level folder if present."""
    logger.info("Unzipping %s ...", archive_path.name)
    dest_root = dest_dir.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        tops = {member.split("/", 1)[0] for member in archive.namelist()}
        strip = f"{tops.pop()}/" if len(tops) == 1 else ""
        for member in archive.infolist():
            rel = member.filename[len(strip):] if member.filename.startswith(strip) else member.filename
            if not rel:
                continue  # the wrapping top-level directory entry itself
            target = (dest_dir / rel).resolve()
            if target != dest_root and dest_root not in target.parents:
                raise click.ClickException(f"Refusing to extract '{member.filename}' outside {dest_dir}.")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(member))
