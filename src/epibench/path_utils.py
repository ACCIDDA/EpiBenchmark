"""Shared helpers for resolving local paths and hub paths."""

from __future__ import annotations

from pathlib import Path

from .gt_from_hub import hub_clone_setup


def resolve_path(path_value: str | Path, base_dir: str | Path | None = None) -> Path:
    """
    Resolve a path, optionally relative to a provided base directory.

    Relative paths are interpreted relative to `base_dir` when provided.
    Otherwise, they are resolved from the current working directory.
    """
    path = Path(path_value).expanduser()
    if not path.is_absolute() and base_dir is not None:
        path = Path(base_dir) / path
    return path.resolve()


def resolve_hub_path(hub_path_value: str, base_dir: str | Path | None = None) -> Path:
    """
    Resolve and validate a local hub path, or clone a GitHub URL.
    """
    if hub_path_value.startswith(("http://", "https://")) and "github.com" in hub_path_value:
        return hub_clone_setup(hub_url=hub_path_value)

    hub_path = resolve_path(hub_path_value, base_dir=base_dir)
    if not hub_path.is_dir():
        raise ValueError(
            f"`hub_path` ({hub_path_value}) either does not exist on this machine "
            "or does not point to a directory."
        )

    target_data_dir = hub_path / "target-data"
    if not target_data_dir.is_dir():
        raise ValueError("`hub_path` does not contain a required 'target-data/' directory.")

    return hub_path
