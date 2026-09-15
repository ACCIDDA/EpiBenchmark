__version__ = "0.0.1"
__author__ = "ACCIDDA"

from .scoring import ScoreResult, score, score_challenge
from .challenge import Challenge
from .creating import create
from .fetching import fetch_challenge
from .library import list_challenges


def __getattr__(name: str):
    """Load Matplotlib-backed API functions only when they are requested."""
    if name in {"plot", "plot_challenge"}:
        from . import plotting

        value = getattr(plotting, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "ScoreResult",
    "Challenge",
    "__author__",
    "__version__",
    "create",
    "fetch_challenge",
    "list_challenges",
    "plot",
    "plot_challenge",
    "score",
    "score_challenge",
]
