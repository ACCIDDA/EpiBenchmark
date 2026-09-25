"""Helpers for tabular inputs accepted as CSV or Parquet files."""

from pathlib import Path

import pandas as pd


TABLE_SUFFIXES = {".csv", ".parquet"}
FORECAST_STRING_COLUMNS = (
    "target",
    "horizon",
    "location",
    "output_type",
    "output_type_id",
    "quantile_level",
)
FORECAST_DATE_COLUMNS = ("reference_date", "target_end_date")
FORECAST_NUMERIC_COLUMNS = ("value", "observation", "observed")


def table_files(directory: Path) -> list[Path]:
    """Find CSV and Parquet files directly inside a directory, in stable order."""
    return sorted(
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in TABLE_SUFFIXES
    )


def read_forecasts(path: str | Path) -> pd.DataFrame:
    """Read a Hubverse forecast CSV or Parquet file with consistent column types.

    Dates are pandas datetimes; horizons, locations, and quantile identifiers
    are strings; forecast values and any observation columns are numeric.
    Other columns retain their source types.
    """
    path = Path(path)
    if path.suffix.lower() == ".csv":
        # Read dates as text first so both formats use the same date conversion.
        text_columns = (*FORECAST_STRING_COLUMNS, *FORECAST_DATE_COLUMNS)
        data = pd.read_csv(path, dtype={column: "string" for column in text_columns})
    elif path.suffix.lower() == ".parquet":
        data = pd.read_parquet(path)
    else:
        raise ValueError(f"Expected a .csv or .parquet file: {path}")

    for column in FORECAST_STRING_COLUMNS:
        if column in data:
            data[column] = data[column].astype("string")
    for column in FORECAST_DATE_COLUMNS:
        if column in data:
            data[column] = pd.to_datetime(data[column], errors="raise")
    for column in FORECAST_NUMERIC_COLUMNS:
        if column in data:
            data[column] = pd.to_numeric(data[column], errors="raise")
    return data
