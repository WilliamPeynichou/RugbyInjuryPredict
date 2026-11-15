"""Absence-reason distribution per season and position (F13 report, aggregated only)."""

from pathlib import Path
from typing import cast

import duckdb
import polars as pl

from rugby_risk.analysis.sequences import K_MIN, suppress_small

SQL = """
select season_id, position_code, absence_reason, n_players, matches_missed
from int_absence_report order by season_id, position_code, absence_reason
"""


def write_report(con: duckdb.DuckDBPyConnection, out: Path) -> Path:
    tables = {r[0] for r in con.execute("show tables").fetchall()}
    if "int_absence_report" not in tables:
        frame = pl.DataFrame(
            schema={
                "season_id": pl.String,
                "position_code": pl.String,
                "absence_reason": pl.String,
                "n_players": pl.Int64,
                "matches_missed": pl.Int64,
            }
        )
    else:
        frame = cast(pl.DataFrame, pl.from_arrow(con.execute(SQL).to_arrow_table()))
    frame = suppress_small(frame)
    lines = [
        "# Motifs d'absence par saison et poste (F13)",
        "",
        f"Cellules de moins de {K_MIN} joueurs supprimées. `injury_candidate` reste dans",
        "`int_absence_runs` mais n'est pas une indisponibilité confirmée.",
        "",
    ]
    if frame.is_empty():
        lines += ["_Aucune absence classée (marts vides ou cellules < 10 joueurs)._"]
    else:
        lines += [
            "| Saison | Poste | Motif | Joueurs | Matchs manqués |",
            "|---|---|---|---|---|",
        ]
        for row in frame.iter_rows():
            lines.append("| " + " | ".join(str(c) for c in row) + " |")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
