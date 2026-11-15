"""Sober matplotlib figures for the descriptive sequence report (aggregated inputs only)."""

from pathlib import Path

import polars as pl
from matplotlib.axes import Axes
from matplotlib.figure import Figure


def _figure() -> tuple[Figure, Axes]:
    """Figure API (no pyplot): no GUI backend, no global state. Sober style: no top/right."""
    fig = Figure(figsize=(8, 4))
    ax = fig.subplots()
    ax.spines[["top", "right"]].set_visible(False)
    return fig, ax


def length_distribution(seqs: pl.DataFrame, path: Path) -> Path:
    """Box plot of sequence lengths per position (no fliers: no individual points shown)."""
    groups = seqs.group_by("position_code").agg("length").sort("position_code")
    fig, ax = _figure()
    ax.boxplot(groups["length"].to_list(), showfliers=False)
    ax.set_xticks(range(1, groups.height + 1), groups["position_code"].to_list(), rotation=30)
    ax.set_ylabel("Matchs consécutifs joués")
    return _save(fig, path)


def season_trend(by_season: pl.DataFrame, path: Path) -> Path:
    fig, ax = _figure()
    for (position,), rows in by_season.group_by("position_code", maintain_order=True):
        ax.plot(
            rows["season_id"].to_list(),
            rows["median_length"].to_list(),
            marker="o",
            label=str(position),
        )
    ax.set_ylabel("Longueur médiane")
    ax.tick_params(axis="x", rotation=30)
    if not by_season.is_empty():
        ax.legend(fontsize=7, ncols=3)
    return _save(fig, path)


def period_effect(by_period: pl.DataFrame, path: Path) -> Path:
    fig, ax = _figure()
    ax.bar(
        by_period["season_period"].to_list(), by_period["median_length"].to_list(), color="#4b6b50"
    )
    ax.set_ylabel("Longueur médiane")
    ax.tick_params(axis="x", rotation=30)
    return _save(fig, path)


def _save(fig: Figure, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    return path
