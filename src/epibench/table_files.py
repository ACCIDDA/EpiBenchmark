"""Helpers for tabular inputs accepted as CSV or Parquet files."""

from pathlib import Path

import pandas as pd


TABLE_SUFFIXES = {".csv", ".parquet"}
FORECAST_STRING_COLUMNS = ("horizon", "location", "output_type_id")


def table_files(directory: Path) -> list[Path]:
    """Find CSV and Parquet files directly inside a directory, in stable order."""
    return sorted(
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in TABLE_SUFFIXES
    )


def read_forecasts(path: str | Path) -> pd.DataFrame:
    """Read a forecast file, preserving horizon, location, and quantile IDs as strings.

    Other columns retain the types inferred by pandas or stored in Parquet.
    Date and numeric validation happens later in the scoring pipeline.
    """
    path = Path(path)
    if path.suffix.lower() == ".csv":
        data = pd.read_csv(
            path, dtype={column: "string" for column in FORECAST_STRING_COLUMNS}
        )
    elif path.suffix.lower() == ".parquet":
        data = pd.read_parquet(path)
    else:
        raise ValueError(f"Expected a .csv or .parquet file: {path}")

    for column in FORECAST_STRING_COLUMNS:
        if column in data:
            data[column] = data[column].astype("string")
    return data
