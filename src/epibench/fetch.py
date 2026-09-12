"""Download EpiBenchmark challenge data files from Zenodo."""

from __future__ import annotations

import json
import logging
import re
import shutil
import zipfile
from pathlib import Path
from typing import Dict, Optional
from urllib.request import Request, urlopen

import click
from bs4 import BeautifulSoup

from .library import is_published, load_challenge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_ZENODO_RECORDS_API = "https://zenodo.org/api/records"
CHALLENGE_DETAILS_FILENAME = "challenge_details.json"


def fetch(challenge_id: str, output_path: Optional[str] = None) -> None:
    """
    Download one library challenge's data files from Zenodo into
    ``<output_path>/<challenge_id>/`` (defaults to the current directory),
    unzipping any archives and keeping a copy of the challenge definition.
    """
    definition = load_challenge(challenge_id)
    challenge_id = Path(challenge_id).stem
    if not is_published(definition):
        raise click.ClickException(
            f"Challenge '{challenge_id}' has not been published to Zenodo yet "
            f"(zenodo_doi is '{definition.get('zenodo_doi')}')."
        )
    # A Zenodo DOI looks like '10.5281/zenodo.1234567'; the record id is the trailing number.
    record_id = str(definition["zenodo_doi"]).rsplit("zenodo.", 1)[-1].strip("/")

    challenge_dir = Path(output_path or ".").expanduser().resolve() / challenge_id
    if challenge_dir.exists():
        raise click.ClickException(
            f"'{challenge_dir}' already exists; remove it or pick another --output-path."
        )
    challenge_dir.mkdir(parents=True)

    try:
        record = _get_json(f"{_ZENODO_RECORDS_API}/{record_id}")
        files = record.get("files") or []
        if not files:
            raise click.ClickException(f"Zenodo record {record_id} contains no files.")
        logger.info("Downloading %d file(s) from Zenodo record %s...", len(files), record_id)
        for file_info in files:
            _download(file_info, challenge_dir)
        for archive in challenge_dir.glob("*.zip"):
            _extract_zip(archive, challenge_dir)
            archive.unlink()
        # keep the challenge definition alongside the data for downstream scoring
        (challenge_dir / f"{challenge_id}.json").write_text(json.dumps(definition, indent=4))

        # keep the record's "Challenge details" Field/Value table (if present) as JSON
        description_html = record.get("metadata", {}).get("description", "")
        challenge_details = _extract_challenge_details_table(description_html)
        if challenge_details:
            (challenge_dir / CHALLENGE_DETAILS_FILENAME).write_text(
                json.dumps(challenge_details, indent=4, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("Saved %s", challenge_dir / CHALLENGE_DETAILS_FILENAME)
        else:
            logger.warning(
                "Could not find a 'Field'/'Value' challenge-details table in the "
                "Zenodo record description for %s; skipping %s.",
                record_id,
                CHALLENGE_DETAILS_FILENAME,
            )
    except BaseException:
        shutil.rmtree(challenge_dir, ignore_errors=True)  # don't leave a partial folder behind
        raise

    logger.info("Challenge '%s' downloaded to %s ✅", challenge_id, challenge_dir)


def _get_json(url: str) -> dict:
    """GET a URL and parse the JSON body, turning network errors into ClickExceptions."""
    try:
        with urlopen(Request(url, headers={"Accept": "application/json"})) as response:
            return json.load(response)
    except OSError as error:  # HTTPError/URLError are OSError subclasses
        raise click.ClickException(f"Could not reach Zenodo ({url}): {error}") from error


def _download(file_info: dict, dest_dir: Path) -> None:
    """Download one Zenodo file entry into ``dest_dir``, showing a progress bar."""
    name, size, url = file_info["key"], file_info["size"], file_info["links"]["self"]
    request = Request(url, headers={"Accept": "*/*", "User-Agent": "epibench"})
    try:
        with urlopen(request) as response, (dest_dir / name).open("wb") as out_file, \
                click.progressbar(length=size, label=f"  {name}", show_pos=True) as bar:
            for chunk in iter(lambda: response.read(1 << 16), b""):
                out_file.write(chunk)
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


def _cell_text(cell) -> str:
    """
    Flatten one <td>/<th> cell to plain text.

    Args:
        cell: a cell in a table.

    Returns:
        string value in a cell.
    """
    return re.sub(r"\s+", " ", cell.get_text()).strip()


def _extract_challenge_details_table(description_html: str) -> Dict[str, str]:
    """
    Parse the "Field" / "Value" challenge-details table out of a Zenodo
    record's HTML ``metadata.description``.

    Args:
        description_html: desciption string.

    Returns: 
        a ``{field: value}`` dict.
    """
    soup = BeautifulSoup(description_html or "", "html.parser")

    for table in soup.find_all("table"):
        rows = [
            [_cell_text(cell) for cell in row.find_all(["th", "td"])]
            for row in table.find_all("tr")
        ]
        rows = [row for row in rows if row]
        if not rows:
            continue
        header = [cell.lower() for cell in rows[0]]
        if header[:2] != ["field", "value"]:
            continue
        return {row[0]: row[1] for row in rows[1:] if len(row) >= 2}

    return {}
