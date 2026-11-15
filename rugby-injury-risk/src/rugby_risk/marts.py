"""Participation marts (F10): dbt build, coverage report and Top 14 minutes quality gate."""

import json
import subprocess
import sys
from pathlib import Path

import duckdb
from dbt.cli.main import dbtRunner

from rugby_risk.injuries.rules import dbt_vars

QUALITY_THRESHOLD = 0.98


def build_marts(staging_dir: Path, log_dir: Path, target_dir: Path) -> bool:
    """Export seeds then `dbt build` every model and test; True when dbt reports success."""
    subprocess.run([sys.executable, "scripts/export_seeds.py"], check=True)
    result = dbtRunner().invoke(
        [
            "build",
            "--project-dir",
            "dbt",
            "--profiles-dir",
            "dbt",
            "--log-path",
            str(log_dir),
            "--target-path",
            str(target_dir),
            "--vars",
            json.dumps({"staging_dir": str(staging_dir), **dbt_vars()}),
        ]
    )
    return bool(result.success)


def low_quality_seasons(con: duckdb.DuckDBPyConnection) -> list[str]:
    rows = con.execute(
        "select season_id from dim_season where quality_flag = 'low' order by season_id"
    ).fetchall()
    return [str(r[0]) for r in rows]


def coverage_markdown(con: duckdb.DuckDBPyConnection) -> str:
    """Matches per season x competition, % with minutes, % passing the minutes check."""
    rows = con.execute(
        """
        select season_id, competition_code, count(*) as matches,
          round(100 * avg(has_minutes::integer), 1) as pct_minutes,
          round(100 * avg(minutes_ok::integer), 1) as pct_ok
        from match_minutes_check
        group by season_id, competition_code
        order by season_id, competition_code
        """
    ).fetchall()
    lines = [
        "# Couverture des matchs (F10)",
        "",
        f"Contrôle des minutes : somme par équipe ∈ [1100, 1300]. Seuil Top 14 : "
        f"{QUALITY_THRESHOLD:.0%} des matchs d'une saison.",
        "",
        "| Saison | Compétition | Matchs | % avec minutes | % contrôle OK |",
        "|---|---|---|---|---|",
    ]
    lines += [f"| {s} | {c} | {n} | {pm} | {ok} |" for s, c, n, pm, ok in rows]
    return "\n".join(lines) + "\n"
