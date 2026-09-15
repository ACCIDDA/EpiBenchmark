__version__ = "0.0.1"
__author__ = "ACCIDDA"

from .scoring import ScoreResult, score, score_challenge


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
    "__author__",
    "__version__",
    "plot",
    "plot_challenge",
    "score",
    "score_challenge",
]
