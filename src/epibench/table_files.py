"""Helpers for tabular inputs accepted as CSV or Parquet files."""

from pathlib import Path

import polars as pl

from .dataframes import to_polars, read_csv


TABLE_SUFFIXES = {".csv", ".parquet"}
FORECAST_STRING_COLUMNS = ("horizon", "location", "output_type_id")


def table_files(directory: Path) -> list[Path]:
    """Find CSV and Parquet files directly inside a directory, in stable order."""
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in TABLE_SUFFIXES
    )


def read_forecasts(path: str | Path) -> pl.DataFrame:
    """Read forecasts, preserving identifiers and exact quantile strings."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        data = read_csv(path, string_columns=FORECAST_STRING_COLUMNS)
    elif path.suffix.lower() == ".parquet":
        data = to_polars(pl.read_parquet(path))
    else:
        raise ValueError(f"Expected a .csv or .parquet file: {path}")
    return data.with_columns(
        [
            pl.col(c).cast(pl.String)
            for c in FORECAST_STRING_COLUMNS
            if c in data.columns
        ]
    )
