"""Helpers for loading score data and building EpiBench plot figures."""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize, TwoSlopeNorm
import numpy as np
import pandas as pd


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


def load_scores(score_file_path: Path) -> pd.DataFrame:
    """
    Read the score CSV, validate the expected schema, and coerce plot types.
    """
    score_df = pd.read_csv(score_file_path, dtype={"location": str})
    score_df.columns = [column.lstrip("\ufeff").strip() for column in score_df.columns]

    missing_columns = REQUIRED_COLUMNS - set(score_df.columns)
    if missing_columns:
        raise KeyError(
            "Score file is missing required columns for plotting: "
            f"{sorted(missing_columns)}"
        )

    score_df = score_df.loc[:, [column for column in score_df.columns if column in REQUIRED_COLUMNS]]

    score_df["model"] = score_df["model"].astype(str).str.strip()
    score_df["location"] = score_df["location"].astype(str).str.strip()
    score_df["reference_date"] = pd.to_datetime(score_df["reference_date"], errors="raise")
    score_df["target_end_date"] = pd.to_datetime(score_df["target_end_date"], errors="raise")
    score_df["horizon"] = pd.to_numeric(score_df["horizon"], errors="raise").astype(int)

    numeric_columns = [
        "wis",
        "overprediction",
        "underprediction",
        "dispersion",
        "rwis",
    ]
    for column in numeric_columns:
        score_df[column] = pd.to_numeric(score_df[column], errors="coerce")

    missing_values = score_df[
        [
            "model",
            "reference_date",
            "target_end_date",
            "location",
            "horizon",
            "wis",
            "overprediction",
            "underprediction",
            "dispersion",
        ]
    ].isna().sum()
    invalid_required = missing_values[missing_values > 0]
    if not invalid_required.empty:
        raise ValueError(
            "Score file contains missing values in required plotting columns: "
            f"{invalid_required.to_dict()}"
        )

    duplicate_count = score_df.duplicated(UNIQUE_KEY_COLUMNS).sum()
    if duplicate_count:
        raise ValueError(
            "Score file contains duplicate forecast-score rows for composite key "
            f"{UNIQUE_KEY_COLUMNS}. Duplicate row count: {duplicate_count}."
        )

    return score_df.sort_values(["reference_date", "target_end_date", "location", "model", "horizon"])


def build_summary_figures(score_df: pd.DataFrame) -> list[plt.Figure]:
    """
    Build the three PDF figures from validated score data.
    """
    return [
        _build_wis_components_figure(score_df),
        _build_rwis_heatmap_figure(score_df),
        _build_reference_date_timeseries_figure(score_df),
    ]


def _build_wis_components_figure(score_df: pd.DataFrame) -> plt.Figure:
    """
    Plot total WIS split into its additive components for each model.
    """
    component_df = (
        score_df.groupby("model", as_index=False)[
            ["wis", "underprediction", "dispersion", "overprediction"]
        ]
        .sum()
        .sort_values("wis", ascending=True)
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
        ax.text(wis_total, y_pos, f" {wis_total:.0f}", va="center", ha="left", fontsize=9)

    ax.set_yticks(y_positions)
    ax.set_yticklabels(component_df["model"])
    ax.invert_yaxis()
    ax.set_xlabel("Total WIS")
    ax.set_title("Plot 1. Total WIS Components by Model")
    ax.legend(loc="lower right")
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    fig.tight_layout()
    return fig


def _build_rwis_heatmap_figure(score_df: pd.DataFrame) -> plt.Figure:
    """
    Plot mean relative WIS by model and forecast horizon.
    """
    rwis_df = score_df.dropna(subset=["rwis"]).copy()
    if rwis_df.empty:
        return _build_empty_figure(
            title="Plot 2. Mean Relative WIS by Model and Horizon",
            message="The score file does not contain any non-missing `rwis` values.",
        )

    heatmap_df = (
        rwis_df.groupby(["model", "horizon"], as_index=False)["rwis"]
        .mean()
        .pivot(index="model", columns="horizon", values="rwis")
    )
    heatmap_df = heatmap_df.loc[heatmap_df.mean(axis=1).sort_values().index]
    heatmap_df = heatmap_df.reindex(sorted(heatmap_df.columns), axis=1)

    values = heatmap_df.to_numpy(dtype=float)
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

    fig_width = max(7, 1.4 * len(heatmap_df.columns))
    fig_height = max(4.5, 0.7 * len(heatmap_df.index))
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    image = ax.imshow(values, aspect="auto", cmap="RdYlBu_r", norm=norm)

    ax.set_xticks(np.arange(len(heatmap_df.columns)))
    ax.set_xticklabels(heatmap_df.columns)
    ax.set_yticks(np.arange(len(heatmap_df.index)))
    ax.set_yticklabels(heatmap_df.index)
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


def _build_reference_date_timeseries_figure(score_df: pd.DataFrame) -> plt.Figure:
    """
    Plot mean WIS over reference date for each model.
    """
    timeseries_df = (
        score_df.groupby(["reference_date", "model"], as_index=False)["wis"]
        .mean()
        .sort_values(["reference_date", "model"])
    )

    model_order = (
        timeseries_df.groupby("model", as_index=False)["wis"]
        .mean()
        .sort_values("wis", ascending=True)["model"]
        .tolist()
    )

    fig, ax = plt.subplots(figsize=(11, 6.5))
    colors = plt.cm.tab10(np.linspace(0, 1, max(len(model_order), 1)))

    for color, model_name in zip(colors, model_order, strict=False):
        model_df = timeseries_df[timeseries_df["model"] == model_name]
        ax.plot(
            model_df["reference_date"],
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
    ax.xaxis.set_major_formatter( mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False)
    fig.tight_layout()
    return fig


def _build_empty_figure(title: str, message: str) -> plt.Figure:
    """
    Create a placeholder figure when a plot cannot be computed from the input.
    """
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.axis("off")
    ax.set_title(title)
    ax.text(0.5, 0.5, message, ha="center", va="center", wrap=True)
    fig.tight_layout()
    return fig
