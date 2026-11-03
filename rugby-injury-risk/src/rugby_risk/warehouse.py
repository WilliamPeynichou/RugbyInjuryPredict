from pathlib import Path

import duckdb
import polars as pl

from rugby_risk.settings import get_settings
from rugby_risk.staging_schemas import SCHEMAS


def connect(path: Path | None = None) -> duckdb.DuckDBPyConnection:
    target = path or get_settings().warehouse_path
    target.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(target))


def write_staging(
    df: pl.DataFrame, entity: str, source: str, season: str, root: Path | None = None
) -> Path:
    """Validate, then write <root>/<entity>/source=<s>/season=<s>/part.parquet (idempotent)."""
    if entity not in SCHEMAS:
        raise ValueError(f"Unknown staging entity: {entity}")
    SCHEMAS[entity].validate(df)
    base = root or get_settings().data_dir / "staging"
    out = base / entity / f"source={source}" / f"season={season}" / "part.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out, compression="zstd")
    return out


def upsert(con: duckdb.DuckDBPyConnection, table: str, df: pl.DataFrame, keys: list[str]) -> None:
    """Delete rows whose keys are in df, then insert df. Table is created on first call."""
    con.register("_incoming", df.to_arrow())
    try:
        con.execute(f'CREATE TABLE IF NOT EXISTS "{table}" AS SELECT * FROM _incoming WHERE false')
        on = " AND ".join(f't."{k}" = i."{k}"' for k in keys)
        con.execute(f'DELETE FROM "{table}" t USING _incoming i WHERE {on}')
        con.execute(f'INSERT INTO "{table}" SELECT * FROM _incoming')
    finally:
        con.unregister("_incoming")
