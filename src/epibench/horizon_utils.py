"""Helpers for working with horizon values."""

from decimal import Decimal, InvalidOperation
from typing import Iterable, List, Set, Union


def normalize_horizon_string(horizon: object) -> str:
    """
    Normalize one horizon value into a canonical string form.
    """
    horizon_text = str(horizon).strip()
    if not horizon_text:
        return horizon_text

    try:
        numeric_horizon = Decimal(horizon_text)
    except InvalidOperation:
        return horizon_text

    if numeric_horizon == numeric_horizon.to_integral():
        return str(int(numeric_horizon))

    return format(numeric_horizon.normalize(), "f")


def normalize_horizon_strings(horizons: Iterable[object]) -> List[str]:
    """Normalize a collection of horizon values into canonical strings."""
    return [normalize_horizon_string(horizon) for horizon in horizons]


def sort_horizon_strings(horizons: Union[Set[str], List[str]]) -> List[str]:
    """
    Sort horizons numerically.
    Useful helper b/c we keep horizons as strs.
    """

    return sorted(
        {normalize_horizon_string(horizon) for horizon in horizons},
        key=lambda horizon: (
            0,
            int(horizon),
        ) if str(horizon).isdigit() else (
            1,
            str(horizon),
        ),
    )
