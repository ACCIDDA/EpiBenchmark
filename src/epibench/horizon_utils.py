"""Helpers for working with horizon values."""

from typing import List, Set, Union


def sort_horizon_strings(horizons: Union[Set[str], List[str]]) -> List[str]:
    """
    Sort horizons numerically.
    Useful helper b/c we keep horizons as strs.
    """
    
    return sorted(
        {str(horizon) for horizon in horizons},
        key=lambda horizon: (
            0,
            int(horizon),
        ) if str(horizon).isdigit() else (
            1,
            str(horizon),
        ),
    )
