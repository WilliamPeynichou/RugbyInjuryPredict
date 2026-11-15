"""Descriptive match-sequence and load aggregates per position and season (F11).

Sequences come from the dbt model `analysis_player_sequences` (macro `consecutive_run_id`,
the only sequence implementation). Every published cell keeps at least K_MIN players.
"""

from pathlib import Path
from typing import cast

import duckdb
import polars as pl

from rugby_risk.analysis.figures import length_distribution, period_effect, season_trend
from rugby_risk.reference import protection_regime

K_MIN = 10
SHORT_TURNAROUND_DAYS = 5
HEAVY_MINUTES = 60

SEQUENCES_SQL = "select player_id, season_id, position_code, start_ts, length from {table}"
APPEARANCES_SQL = """
select a.player_id, m.season_id, coalesce(d.primary_position, a.position_played) as position_code,
  m.kickoff_ts, a.is_starter, a.minutes_played, e.played
from fact_appearance a
join fact_match m using (match_id)
join fact_eligibility e using (match_id, player_id)
left join dim_player d using (player_id)
"""


def suppress_small(frame: pl.DataFrame, k: int = K_MIN) -> pl.DataFrame:
    """k-anonymity: drop every aggregated cell built on fewer than k distinct players."""
    return frame.filter(pl.col("n_players") >= k)


def sequence_stats(seqs: pl.DataFrame, by: list[str]) -> pl.DataFrame:
    return (
        seqs.group_by(by)
        .agg(
            pl.col("player_id").n_unique().alias("n_players"),
            pl.col("length").median().alias("median_length"),
            pl.col("length").quantile(0.9, "nearest").alias("p90_length"),
            pl.col("length").max().alias("max_length"),
        )
        .sort(by)
    )


def load_stats(apps: pl.DataFrame) -> pl.DataFrame:
    """Per position x season: minutes per player, share of starts >= 60', short turnarounds."""
    played = apps.filter(pl.col("played").fill_null(False)).sort("player_id", "kickoff_ts")
    played = played.with_columns(
        (pl.col("kickoff_ts").diff().over("player_id", "season_id").dt.total_days())
        .lt(SHORT_TURNAROUND_DAYS)
        .fill_null(False)
        .alias("short_turnaround")
    )
    per_player = played.group_by("player_id", "season_id", "position_code").agg(
        pl.col("minutes_played").sum().alias("season_minutes"),
        pl.col("short_turnaround").sum().alias("short_turnarounds"),
    )
    starts = (
        apps.filter(pl.col("is_starter") & pl.col("minutes_played").is_not_null())
        .group_by("position_code", "season_id")
        .agg((pl.col("minutes_played") >= HEAVY_MINUTES).mean().alias("share_starts_60"))
    )
    return (
        per_player.group_by("position_code", "season_id")
        .agg(
            pl.col("player_id").n_unique().alias("n_players"),
            pl.col("season_minutes").median().alias("median_season_minutes"),
            pl.col("short_turnarounds").mean().alias("mean_short_turnarounds"),
        )
        .join(starts, on=["position_code", "season_id"], how="left")
        .sort("position_code", "season_id")
    )


def with_period(seqs: pl.DataFrame) -> pl.DataFrame:
    """season_period = FFR/LNR protection regime in force at the sequence start."""
    return seqs.with_columns(
        pl.col("start_ts")
        .dt.date()
        .map_elements(protection_regime, return_dtype=pl.String)
        .alias("season_period")
    )


def _markdown(frame: pl.DataFrame) -> list[str]:
    if frame.is_empty():
        return ["_Aucune cellule avec au moins 10 joueurs._", ""]
    rows = [" | ".join(str(v) for v in row) for row in frame.iter_rows()]
    header = " | ".join(frame.columns)
    sep = " | ".join("---" for _ in frame.columns)
    return [f"| {header} |", f"| {sep} |", *(f"| {r} |" for r in rows), ""]


def build_report(seqs: pl.DataFrame, apps: pl.DataFrame, fig_dir: Path) -> str:
    """Markdown report, aggregated only (k >= K_MIN players per cell); figures in fig_dir."""
    lines = [
        "# Séquences de matchs et charge par poste (F11)",
        "",
        "Données de participation uniquement, aucune donnée de blessure. Séquence = matchs "
        "consécutifs de l'équipe du joueur où il a joué au moins une minute (docs/05 §2). "
        f"Cellules de moins de {K_MIN} joueurs supprimées.",
        "",
    ]
    if seqs.is_empty():
        return "\n".join([*lines, "_Aucune séquence : marts de participation vides._"]) + "\n"
    seqs = with_period(seqs)
    by_position = suppress_small(sequence_stats(seqs, ["position_code"]))
    by_season = suppress_small(sequence_stats(seqs, ["position_code", "season_id"]))
    by_period = suppress_small(sequence_stats(seqs, ["season_period"]))
    load = pl.DataFrame() if apps.is_empty() else suppress_small(load_stats(apps))
    fig_dir.mkdir(parents=True, exist_ok=True)
    kept = seqs.filter(pl.col("position_code").is_in(by_position["position_code"].implode()))
    figures = [
        length_distribution(kept, fig_dir / "sequence_length_by_position.png"),
        season_trend(by_season, fig_dir / "median_length_by_season.png"),
        period_effect(by_period, fig_dir / "length_by_period.png"),
    ]
    lines += ["## Longueur des séquences par poste", "", *_markdown(by_position)]
    lines += ["## Par poste et saison", "", *_markdown(by_season)]
    lines += ["## Par période réglementaire (FFR/LNR)", "", *_markdown(by_period)]
    lines += ["## Charge par poste et saison", "", *_markdown(load)]
    lines += ["## Figures", ""] + [f"![{p.stem}]({p.parent.name}/{p.name})" for p in figures]
    return "\n".join(lines) + "\n"


def _query(con: duckdb.DuckDBPyConnection, sql: str) -> pl.DataFrame:
    return cast(pl.DataFrame, pl.from_arrow(con.execute(sql).to_arrow_table()))


def write_report(con: duckdb.DuckDBPyConnection, out: Path) -> Path:
    tables = {r[0] for r in con.execute("show tables").fetchall()}
    if "analysis_player_sequences" in tables:
        seqs = _query(con, SEQUENCES_SQL.format(table="analysis_player_sequences"))
        apps = _query(con, APPEARANCES_SQL)
    else:
        seqs, apps = pl.DataFrame(), pl.DataFrame()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_report(seqs, apps, out.parent / "figures"), encoding="utf-8")
    return out
