"""Export of `ml_player_match` for modelling (F17): parquet + VERSION + profile report."""

from pathlib import Path

import duckdb

from rugby_risk.features.registry import ALL_COLUMNS, FEATURES, FORBIDDEN_COLUMNS


class MLTableError(RuntimeError):
    """The warehouse table does not match the registry (columns or pseudonymisation)."""


def check_columns(con: duckdb.DuckDBPyConnection) -> list[str]:
    columns = [r[0] for r in con.execute("describe ml_player_match").fetchall()]
    if forbidden := FORBIDDEN_COLUMNS & set(columns):
        raise MLTableError(f"Colonnes nominatives dans ml_player_match: {sorted(forbidden)}")
    if set(columns) != set(ALL_COLUMNS) or len(columns) != len(ALL_COLUMNS):
        diff = sorted(set(columns) ^ set(ALL_COLUMNS))
        raise MLTableError(f"ml_player_match diffère du registre: {diff}")
    return columns


def export(con: duckdb.DuckDBPyConnection, out_dir: Path) -> tuple[Path, str]:
    """Write data/ml/ml_player_match.parquet (registry column order) and data/ml/VERSION."""
    check_columns(con)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "ml_player_match.parquet"
    cols = ", ".join(ALL_COLUMNS)
    con.execute(
        f"copy (select {cols} from ml_player_match order by kickoff_ts, match_id, player_key)"
        f" to '{path}' (format parquet, compression zstd)"
    )
    row = con.execute("select any_value(dataset_version) from ml_player_match").fetchone()
    version = str(row[0]) if row and row[0] else "empty"
    (out_dir / "VERSION").write_text(version + "\n", encoding="utf-8")
    return path, version


def profile_markdown(con: duckdb.DuckDBPyConnection) -> str:
    """Rows per season, y_injury prevalence by position group, missing rate per feature."""
    seasons = con.execute(
        """select season_id, count(*), sum(played::integer),
          round(100 * avg(y_injury::integer) filter (where played), 2)
        from ml_player_match group by 1 order by 1"""
    ).fetchall()
    groups = con.execute(
        """select coalesce(position_group, 'unknown'), sum(played::integer),
          sum(y_injury::integer), round(100 * avg(y_injury::integer) filter (where played), 2)
        from ml_player_match group by 1 order by 1"""
    ).fetchall()
    nulls = ", ".join(f"avg(({c} is null)::integer) as {c}" for c in FEATURES)
    missing = con.execute(f"select {nulls} from ml_player_match").fetchone() or ()
    lines = [
        "# Profil de la table ml_player_match (F17)",
        "",
        "Agrégats uniquement (aucune ligne joueur). Prévalence = % de matchs joués avec blessure.",
        "",
        "| Saison | Lignes | Matchs joués | Prévalence y_injury (%) |",
        "|---|---|---|---|",
        *[f"| {s} | {n} | {p} | {v} |" for s, n, p, v in seasons],
        "",
        "| Groupe de poste | Matchs joués | Blessures | Prévalence (%) |",
        "|---|---|---|---|",
        *[f"| {g} | {p} | {y} | {v} |" for g, p, y, v in groups],
        "",
        "| Feature | % manquant |",
        "|---|---|",
        *[f"| {c} | {100 * (m or 0):.1f} |" for c, m in zip(FEATURES, missing, strict=True) if m],
    ]
    return "\n".join(lines) + "\n"
