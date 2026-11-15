"""Calibration report: distribution of starter exit minutes per position group (F12)."""

from pathlib import Path
from typing import cast

import duckdb
import polars as pl

SQL = """
select
  p.position_group,
  count(*) as n_exits,
  count(*) filter (where a.minute_off <= 80) as n_before_80,
  quantile(a.minute_off, 0.1) as p10,
  quantile(a.minute_off, 0.25) as p25,
  median(a.minute_off) as p50,
  quantile(a.minute_off, 0.75) as p75
from fact_appearance a
left join dim_player d using (player_id)
left join ref_positions p on p.position_code = coalesce(d.primary_position, a.position_played)
where a.is_starter and a.minute_off is not null
group by p.position_group order by p.position_group
"""


def exit_distribution(con: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    # Entrepôt sans marts (pas de run réel) : rapport vide plutôt qu'une erreur.
    tables = {r[0] for r in con.execute("show tables").fetchall()}
    if "fact_appearance" not in tables:
        return pl.DataFrame(
            schema={
                "position_group": pl.String,
                "n_exits": pl.Int64,
                "n_before_80": pl.Int64,
                "p10": pl.Float64,
                "p25": pl.Float64,
                "p50": pl.Float64,
                "p75": pl.Float64,
            }
        )
    return cast(pl.DataFrame, pl.from_arrow(con.execute(SQL).to_arrow_table()))


def write_report(con: duckdb.DuckDBPyConnection, out: Path) -> Path:
    frame = exit_distribution(con)
    lines = [
        "# Calibrage des sorties de match (F12)",
        "",
        "Ajustement humain des seuils de `config/injury_rules.yaml` (`early_exit_minute`,",
        "`very_early_minute`). Minute de sortie des titulaires uniquement (minute_off).",
        "",
    ]
    if frame.is_empty():
        lines += ["_Aucune sortie de match mesurée (minutes manquantes)._"]
    else:
        lines += [
            "| Groupe de poste | Sorties | ≤ 80' | P10 | P25 | Médiane | P75 |",
            "|---|---|---|---|---|---|---|",
        ]
        for row in frame.iter_rows(named=True):
            cells = [
                row["position_group"],
                row["n_exits"],
                row["n_before_80"],
                row["p10"],
                row["p25"],
                row["p50"],
                row["p75"],
            ]
            lines.append("| " + " | ".join(str(c) for c in cells) + " |")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
