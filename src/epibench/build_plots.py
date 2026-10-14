"""Logic for loading score data and building EpiBench plots."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize, TwoSlopeNorm
import numpy as np
import polars as pl

from .dataframes import to_polars, normalize_dates, read_csv
import logging

logger = logging.getLogger(__name__)


REQUIRED_COLUMNS = {
    "model",
    "reference_date",
    "target_end_date",
    "location",
    "horizon",
    "wis",
    "overprediction",
    "underprediction",
    "dispersion",
    "rwis",
}

UNIQUE_KEY_COLUMNS = [
    "target_end_date",
    "model",
    "reference_date",
    "location",
    "horizon",
]

COMPONENT_COLORS = {
    "underprediction": "#55a868",
    "dispersion": "#4c72b0",
    "overprediction": "#c44e52",
}


def load_scores(score_file_path: Path) -> pl.DataFrame:
    """
    Read a score CSV and pass it through the shared plotting validation.
    """
    return validate_scores(read_scores(score_file_path))


def read_scores(score_file_path: Path) -> pl.DataFrame:
    """
    Read a score CSV.
    Specifically preserves location identifiers as strings.
    """
    return read_csv(score_file_path, string_columns=("location",))


def validate_scores(score_df: Any) -> pl.DataFrame:
    """Validate and normalize any supported frame for plotting."""
    score_df = to_polars(score_df)
    score_df = score_df.rename(
        {c: c.lstrip("\ufeff").strip() for c in score_df.columns}
    )
    missing_columns = REQUIRED_COLUMNS - set(score_df.columns)
    if missing_columns:
        raise KeyError(
            f"Score file is missing required columns for plotting: {sorted(missing_columns)}"
        )
    score_df = score_df.select([c for c in score_df.columns if c in REQUIRED_COLUMNS])
    score_df = normalize_dates(score_df, ["reference_date", "target_end_date"])
    score_df = score_df.with_columns(
        pl.col("model", "location").cast(pl.String).str.strip_chars(),
        pl.col("horizon").cast(pl.Float64).cast(pl.Int64),
        pl.col("wis", "overprediction", "underprediction", "dispersion", "rwis")
        .cast(pl.Float64, strict=False)
        .fill_nan(None),
    )
    required = [c for c in score_df.columns if c != "rwis"]
    missing_values = score_df.select(required).null_count().row(0, named=True)
    invalid_required = {c: n for c, n in missing_values.items() if n}
    if invalid_required:
        raise ValueError(
            f"Score file contains missing values in required plotting columns: {invalid_required}"
        )
    duplicate_count = (
        score_df.height - score_df.unique(subset=UNIQUE_KEY_COLUMNS).height
    )
    if duplicate_count:
        raise ValueError(
            "Score file contains duplicate forecast-score rows for composite key "
            f"{UNIQUE_KEY_COLUMNS}. Duplicate row count: {duplicate_count}."
        )
    logger.info("Success ✅")
    return score_df.sort(
        ["reference_date", "target_end_date", "location", "model", "horizon"],
        maintain_order=True,
    )


def build_summary_figures(score_df: pl.DataFrame) -> list[plt.Figure]:
    """
    Build the three PDF figures from validated score data.
    """
    return [
        _build_wis_components_figure(score_df),
        _build_rwis_heatmap_figure(score_df),
        _build_reference_date_timeseries_figure(score_df),
    ]


def _build_wis_components_figure(score_df: pl.DataFrame) -> plt.Figure:
    """
    Plot total WIS split into its additive components for each model.
    """
    component_df = (
        score_df.group_by("model")
        .agg(pl.col("wis", "underprediction", "dispersion", "overprediction").sum())
        .sort(["wis", "model"], maintain_order=True)
    )

    fig_height = max(4.5, 0.7 * len(component_df))
    fig, ax = plt.subplots(figsize=(11, fig_height))

    left = np.zeros(len(component_df))
    y_positions = np.arange(len(component_df))
    for column in ["underprediction", "dispersion", "overprediction"]:
        ax.barh(
            y_positions,
            component_df[column],
            left=left,
            color=COMPONENT_COLORS[column],
            label=column.replace("_", " ").title(),
        )
        left += component_df[column].to_numpy()

    for y_pos, wis_total in zip(y_positions, component_df["wis"], strict=True):
        ax.text(
            wis_total, y_pos, f" {wis_total:.0f}", va="center", ha="left", fontsize=9
        )

    ax.set_yticks(y_positions)
    ax.set_yticklabels(component_df["model"])
    ax.invert_yaxis()
    ax.set_xlabel("Total WIS")
    ax.set_title("Plot 1. Total WIS Components by Model")
    ax.legend(loc="lower right")
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    fig.tight_layout()
    return fig


def _build_rwis_heatmap_figure(score_df: pl.DataFrame) -> plt.Figure:
    """
    Plot mean relative WIS by model and forecast horizon.
    """
    rwis_df = score_df.drop_nulls("rwis")
    if rwis_df.is_empty():
        return _build_empty_figure(
            title="Plot 2. Mean Relative WIS by Model and Horizon",
            message="The score file does not contain any non-missing `rwis` values.",
        )

    means = rwis_df.group_by(["model", "horizon"]).agg(pl.col("rwis").mean())
    horizons = sorted(means["horizon"].unique().to_list())
    heatmap_df = means.pivot(on="horizon", index="model", values="rwis")
    value_columns = [str(h) for h in horizons]
    heatmap_df = (
        heatmap_df.with_columns(pl.mean_horizontal(value_columns).alias("_mean"))
        .sort(["_mean", "model"])
        .drop("_mean")
    )
    models = heatmap_df["model"].to_list()
    values = heatmap_df.select(value_columns).to_numpy()
    finite_values = values[np.isfinite(values)]
    if finite_values.size == 0:
        return _build_empty_figure(
            title="Plot 2. Mean Relative WIS by Model and Horizon",
            message="The score file does not contain any finite `rwis` values to plot.",
        )

    vmin = finite_values.min()
    vmax = finite_values.max()
    if vmin < 1.0 < vmax:
        norm = TwoSlopeNorm(vmin=vmin, vcenter=1.0, vmax=vmax)
    else:
        norm = Normalize(vmin=vmin, vmax=vmax)

    fig_width = max(7, 1.4 * len(horizons))
    fig_height = max(4.5, 0.7 * len(models))
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    image = ax.imshow(values, aspect="auto", cmap="RdYlBu_r", norm=norm)

    ax.set_xticks(np.arange(len(horizons)))
    ax.set_xticklabels(horizons)
    ax.set_yticks(np.arange(len(models)))
    ax.set_yticklabels(models)
    ax.set_xlabel("Horizon")
    ax.set_ylabel("Model")
    ax.set_title("Plot 2. Mean Relative WIS by Model and Horizon")

    for row_index in range(values.shape[0]):
        for column_index in range(values.shape[1]):
            cell_value = values[row_index, column_index]
            if np.isfinite(cell_value):
                ax.text(
                    column_index,
                    row_index,
                    f"{cell_value:.2f}",
                    ha="center",
                    va="center",
                    color="black",
                    fontsize=9,
                )

    colorbar = fig.colorbar(image, ax=ax, shrink=0.9)
    colorbar.set_label("Mean RWIS (lower is better; baseline = 1.0)")
    fig.tight_layout()
    return fig


def _build_reference_date_timeseries_figure(score_df: pl.DataFrame) -> plt.Figure:
    """
    Plot mean WIS over reference date for each model.
    """
    timeseries_df = (
        score_df.group_by(["reference_date", "model"])
        .agg(pl.col("wis").mean())
        .sort(["reference_date", "model"])
    )
    model_order = (
        timeseries_df.group_by("model")
        .agg(pl.col("wis").mean())
        .sort(["wis", "model"])["model"]
        .to_list()
    )

    fig, ax = plt.subplots(figsize=(11, 6.5))
    colors = plt.cm.tab10(np.linspace(0, 1, max(len(model_order), 1)))

    for color, model_name in zip(colors, model_order, strict=False):
        model_df = timeseries_df.filter(pl.col("model") == model_name)
        ax.plot(
            model_df["reference_date"].to_numpy(),
            model_df["wis"],
            linewidth=2,
            marker="o",
            markersize=3,
            color=color,
            label=model_name,
        )

    ax.set_title("Plot 3. Mean WIS by Reference Date")
    ax.set_xlabel("Reference Date")
    ax.set_ylabel("Mean WIS")
    ax.grid(axis="both", linestyle=":", alpha=0.4)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(
        mdates.ConciseDateFormatter(ax.xaxis.get_major_locator())
    )
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False)
    fig.tight_layout()
    return fig


def _build_empty_figure(title: str, message: str) -> plt.Figure:
    """
    Create a placeholder figure when a plot cannot be computed from the input.
    Allows other plots to be built independ of one another. Prevents immediate
    fail and exit if one plot fails.
    """
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.axis("off")
    ax.set_title(title)
    ax.text(0.5, 0.5, message, ha="center", va="center", wrap=True)
    fig.tight_layout()
    return fig
