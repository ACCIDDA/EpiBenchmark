"""Helpers for tabular inputs accepted as CSV or Parquet files."""

from pathlib import Path

import pandas as pd


TABLE_SUFFIXES = {".csv", ".parquet"}


def table_files(directory: Path) -> list[Path]:
    """Find CSV and Parquet files directly inside a directory, in stable order."""
    return sorted(
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in TABLE_SUFFIXES
    )


def read_table(path: Path, *, string_columns: tuple[str, ...] = ()) -> pd.DataFrame:
    """Read either format and preserve identifier columns as strings."""
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype={column: str for column in string_columns})
    if path.suffix.lower() == ".parquet":
        data = pd.read_parquet(path)
        for column in string_columns:
            if column in data:
                data[column] = data[column].astype("string")
        return data
    raise ValueError(f"Expected a .csv or .parquet file: {path}")
