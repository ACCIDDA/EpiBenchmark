"""Convert public tabular inputs and normalize shared types."""

from datetime import date, datetime
from typing import Any

import polars as pl
import pyarrow as pa
from dateutil.parser import parse as parse_date


def is_dataframe(data: Any) -> bool:
    """Recognize frames and standard dataframe/Arrow interchange providers."""
    return isinstance(
        data, (pl.DataFrame, pl.LazyFrame, pa.Table, pa.RecordBatch)
    ) or any(
        hasattr(data, name)
        for name in ("__dataframe__", "__arrow_c_stream__", "to_arrow")
    )


def to_polars(data: Any) -> pl.DataFrame:
    """Convert supported tabular inputs to an eager DataFrame.

    Row indexes are not forecast columns.
    NaN becomes null so missing-value behavior is consistent across providers.
    """
    if isinstance(data, pl.DataFrame):
        frame = data.clone()
    elif isinstance(data, pl.LazyFrame):
        frame = data.collect()
    elif any(
        base.__module__.split(".")[0] == "pandas" and base.__name__ == "DataFrame"
        for base in type(data).__mro__
    ):
        frame = pl.from_pandas(data, include_index=False)
    elif isinstance(data, (pa.Table, pa.RecordBatch)):
        frame = pl.from_arrow(data)
    elif hasattr(data, "__arrow_c_stream__"):
        frame = pl.DataFrame(data)
    elif hasattr(data, "to_arrow"):
        frame = pl.from_arrow(data.to_arrow())
    elif hasattr(data, "__dataframe__"):
        frame = pl.from_dataframe(data)
    else:
        raise TypeError(
            "Expected a DataFrame supporting Polars, Arrow, or the dataframe "
            f"interchange protocol; received {type(data).__name__}."
        )
    return frame.with_columns(pl.col(pl.Float32, pl.Float64).fill_nan(None))


def date_value(value: Any) -> datetime:
    """Convert a scalar date used for evaluation bounds."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(
        tzinfo=None
    )


def normalize_dates(
    frame: pl.DataFrame,
    columns: list[str] | tuple[str, ...],
    *,
    strings: bool = False,
    strict: bool = True,
) -> pl.DataFrame:
    """Parse mixed date/date-time representations without a row-wise hot path."""
    replacements = []
    for column in columns:
        source = frame[column]
        dtype = source.dtype
        if dtype == pl.Date or isinstance(dtype, pl.Datetime):
            if isinstance(dtype, pl.Datetime) and dtype.time_zone is not None:
                source = source.dt.replace_time_zone(None)
            parsed = source.cast(pl.Datetime("us"))
        elif dtype.is_numeric():
            # Numeric timestamps represent nanoseconds since epoch.
            parsed = (
                source.cast(pl.Int64).cast(pl.Datetime("ns")).cast(pl.Datetime("us"))
            )
        else:
            text = source.cast(pl.String).str.strip_chars()
            fast = pl.coalesce(
                pl.col(column).str.to_datetime(format=fmt, strict=False)
                for fmt in (
                    "%Y-%m-%d",
                    "%Y-%m-%d %H:%M:%S%.f",
                    "%Y-%m-%dT%H:%M:%S%.f",
                    "%m/%d/%Y",
                    "%Y/%m/%d",
                    "%Y%m%d",
                )
            )
            parsed = pl.DataFrame({column: text}).select(fast).to_series()
            unresolved = text.filter(text.is_not_null() & parsed.is_null()).unique()
            if len(unresolved):
                # Preserve flexible date inputs without parsing every row in Python.
                lookup = {}
                for value in unresolved:
                    if value in ("NaT", "nan", "NaN"):
                        lookup[value] = None
                        continue
                    try:
                        lookup[value] = parse_date(
                            value, default=datetime(1, 1, 1)
                        ).replace(tzinfo=None)
                    except (TypeError, ValueError, OverflowError) as error:
                        if strict:
                            raise ValueError(
                                f"`{column}` contains an invalid date."
                            ) from error
                        lookup[value] = None
                fallback = text.replace_strict(
                    lookup, default=None, return_dtype=pl.Datetime("us")
                )
                parsed = parsed.fill_null(fallback)
        if strings:
            parsed = parsed.dt.strftime("%Y-%m-%d")
        replacements.append(parsed.alias(column))
    return frame.with_columns(replacements)


# Recognize CSV missing tokens while preserving identifier strings.
CSV_NULL_VALUES = [
    "",
    "#N/A",
    "#N/A N/A",
    "#NA",
    "-1.#IND",
    "-1.#QNAN",
    "-NaN",
    "-nan",
    "1.#IND",
    "1.#QNAN",
    "<NA>",
    "N/A",
    "NA",
    "NULL",
    "NaN",
    "None",
    "n/a",
    "nan",
    "null",
]


def read_csv(path: Any, *, string_columns: tuple[str, ...] = ()) -> pl.DataFrame:
    """Read CSVs with full-file inference and explicit missing tokens."""
    return pl.read_csv(
        path,
        schema_overrides={name: pl.String for name in string_columns},
        infer_schema_length=None,
        null_values=CSV_NULL_VALUES,
    ).with_columns(pl.col(pl.Float32, pl.Float64).fill_nan(None))
