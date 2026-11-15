"""Player entity resolution asset: dim_player + player_source_xref in DuckDB."""

import fcntl
from contextlib import closing, contextmanager
from pathlib import Path
from typing import cast

import duckdb
import polars as pl
from dagster import (
    AssetCheckResult,
    AssetCheckSeverity,
    AssetExecutionContext,
    Output,
    asset,
    asset_check,
)

from orchestration.partitions import season_partitions
from rugby_risk.entity_resolution.anchor import anchor_pairs
from rugby_risk.entity_resolution.invariants import (
    check_no_double_sheet_same_day,
    check_stable_ids,
    check_unique_source_id,
)
from rugby_risk.entity_resolution.records import build_records, pick_player_fields
from rugby_risk.entity_resolution.resolve import resolve_entities
from rugby_risk.entity_resolution.review import write_review_queue
from rugby_risk.entity_resolution.splink_model import AUTO_LINK, REVIEW, score_pairs
from rugby_risk.privacy import player_key
from rugby_risk.reference import position_canonical, positions
from rugby_risk.settings import get_settings
from rugby_risk.warehouse import connect

# DuckDB n'autorise qu'une connexion RW par fichier ; l'exécuteur Dagster est
# multiprocessus, on sérialise donc l'accès avec un verrou fichier (POSIX).
_LOCK_PATH = Path("data/warehouse.lock")


@contextmanager
def warehouse_lock():
    _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK_PATH.open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


@contextmanager
def _locked_connect():
    with warehouse_lock(), closing(connect()) as con:
        yield con


XREF_TABLE = "player_source_xref"
DIM_TABLE = "er_dim_player"


def _staging_frames(staging: Path, entity: str, columns: list[str]) -> list[pl.DataFrame]:
    paths = sorted((staging / entity).glob("source=*/season=*/part.parquet"))
    return [pl.read_parquet(path).select(columns) for path in paths]


def _load_inputs() -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    staging = get_settings().data_dir / "staging"
    match_cols = [
        "source",
        "source_match_id",
        "competition_code",
        "season_id",
        "kickoff_ts",
        "home_team_name",
        "away_team_name",
    ]
    app_cols = [
        "source",
        "source_match_id",
        "source_player_id",
        "player_name",
        "team_name",
        "shirt_number",
    ]
    profile_cols = [
        "source",
        "source_player_id",
        "full_name",
        "birth_date",
        "height_cm",
        "weight_kg",
        "nationality",
        "jiff",
        "positions_raw",
    ]
    matches = pl.concat(_staging_frames(staging, "match", match_cols), how="vertical_relaxed")
    apps = pl.concat(_staging_frames(staging, "appearance", app_cols), how="vertical_relaxed")
    profiles = pl.concat(
        _staging_frames(staging, "player_profile", profile_cols), how="vertical_relaxed"
    )
    return matches, apps, profiles


def _resolve() -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Shared pipeline for the asset and the asset checks: inputs -> xref + dim."""
    matches, apps, profiles = _load_inputs()
    records, appearances, anchor_apps = build_records(matches, apps, profiles)
    anchor = anchor_pairs(anchor_apps)
    with _locked_connect() as con:
        previous = _read_table(con, XREF_TABLE)
    if previous is not None:
        previous = previous.with_columns(
            pl.concat_str([pl.col("source"), pl.lit(":"), pl.col("source_player_id")]).alias("key")
        )
    overrides = (
        pl.read_csv("data/reference/er_overrides.csv", infer_schema=False)
        .with_columns(
            pl.concat_str([pl.col("source"), pl.lit(":"), pl.col("source_player_id")]).alias("key")
        )
        .select("key", "player_id")
    )
    scored = score_pairs(records, threshold=REVIEW)
    xref, queue = resolve_entities(
        records,
        anchor,
        scored,
        appearances,
        previous,
        overrides,
        auto_link=AUTO_LINK,
        review=REVIEW,
    )
    return xref, queue, records, appearances, profiles


def _read_table(con: duckdb.DuckDBPyConnection, table: str) -> pl.DataFrame | None:
    names = con.execute("show tables").fetchall()
    if (table,) not in names:
        return None
    result = con.execute(f'select * from "{table}"').to_arrow_table()
    return cast(pl.DataFrame, pl.from_arrow(result))


def _replace(con: duckdb.DuckDBPyConnection, table: str, frame: pl.DataFrame) -> None:
    con.execute(f'drop table if exists "{table}"')
    con.register("_new", frame.to_arrow())
    con.execute(f'create table "{table}" as select * from _new')
    con.unregister("_new")


def _dim_player(xref: pl.DataFrame, records: pl.DataFrame, profiles: pl.DataFrame) -> pl.DataFrame:
    schema = {
        "player_id": pl.Int64,
        "player_key": pl.String,
        "full_name": pl.String,
        "birth_date": pl.Date,
        "height_cm": pl.Int64,
        "weight_kg": pl.Int64,
        "nationality": pl.String,
        "jiff": pl.Boolean,
        "primary_position": pl.String,
        "position_group": pl.String,
        "unit": pl.String,
    }
    players = pick_player_fields(records, profiles, xref)
    if players.is_empty():
        return pl.DataFrame(schema=schema)
    players = players.with_columns(
        pl.col("player_id").map_elements(player_key, return_dtype=pl.String).alias("player_key")
    )

    def first_position(raw: str | None, source: str) -> str | None:
        if raw is None:
            return None
        tokens = (t.strip() for t in raw.replace(";", ",").split(","))
        return next(
            (code for t in tokens if (code := position_canonical(t, source)) is not None),
            None,
        )

    primary = (
        profiles.with_columns(
            pl.concat_str([pl.col("source"), pl.lit(":"), pl.col("source_player_id")]).alias("key")
        )
        .join(xref.select("key", "player_id"), on="key")
        .filter(pl.col("positions_raw").is_not_null())
        .with_columns(
            pl.struct(["positions_raw", "source"])
            .map_elements(
                lambda r: first_position(r["positions_raw"], r["source"]),
                return_dtype=pl.String,
            )
            .alias("primary_position")
        )
        .group_by("player_id")
        .agg(pl.col("primary_position").drop_nulls().first().alias("primary_position"))
        .select("player_id", "primary_position")
    )
    players = players.join(primary, on="player_id", how="left").join(
        positions().select("position_code", "position_group", "unit"),
        left_on="primary_position",
        right_on="position_code",
        how="left",
    )
    return players.select(*schema.keys())


@asset(partitions_def=season_partitions, compute_kind="python")
def player_entities(context: AssetExecutionContext) -> Output:
    """Resolve player identities across sources; persist xref + dim_player in DuckDB."""
    xref, queue, records, _appearances, profiles = _resolve()
    con = connect()
    previous = _read_table(con, XREF_TABLE)
    if previous is not None:
        _replace(con, "player_source_xref_prev", previous)
    _replace(con, XREF_TABLE, xref.drop("key"))
    dim = _dim_player(xref, records, profiles)
    _replace(con, DIM_TABLE, dim)
    queue_path = write_review_queue(queue)
    counts = xref.group_by("method").len().to_dicts()
    context.log.info("Résolution: %s", counts)
    report_dir = get_settings().data_dir / "staging" / "_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# er_quality",
        "",
        f"- player_ids: {dim.height}",
        f"- records: {records.height}",
        f"- review queue: {queue.height} paires ({queue_path})",
    ] + [f"- {c['method']}: {c['len']}" for c in counts]
    (report_dir / "er_quality.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return Output(
        None,
        metadata={
            "players": dim.height,
            "records": records.height,
            "review_pairs": queue.height,
        },
    )


def _check_result(violations: pl.DataFrame) -> AssetCheckResult:
    # pas de check_name explicite : Dagster résout le nom depuis la fonction du décorateur.
    return AssetCheckResult(
        passed=violations.is_empty(),
        severity=AssetCheckSeverity.WARN,
        metadata={"violations": violations.height},
    )


@asset_check(asset=player_entities)
def er_unique_source_id() -> AssetCheckResult:
    with _locked_connect() as con:
        xref = _read_table(con, XREF_TABLE)
    if xref is None:
        return AssetCheckResult(passed=True, metadata={"violations": 0})
    return _check_result(check_unique_source_id(xref))


@asset_check(asset=player_entities)
def er_no_double_sheet_same_day() -> AssetCheckResult:
    with _locked_connect() as con:
        if _read_table(con, XREF_TABLE) is None:
            return AssetCheckResult(passed=True, metadata={"violations": 0})
    xref, _, _, appearances, _ = _resolve()
    violations = check_no_double_sheet_same_day(xref, appearances, None)
    return _check_result(violations)


@asset_check(asset=player_entities)
def er_stable_ids() -> AssetCheckResult:
    with _locked_connect() as con:
        current = _read_table(con, XREF_TABLE)
        previous = _read_table(con, "player_source_xref_prev")
    if current is None or previous is None:
        return AssetCheckResult(passed=True, metadata={"violations": 0})

    def keyed(frame: pl.DataFrame) -> pl.DataFrame:
        return frame.with_columns(
            pl.concat_str([pl.col("source"), pl.lit(":"), pl.col("source_player_id")]).alias("key")
        ).select("key", "player_id")

    return _check_result(check_stable_ids(keyed(current), keyed(previous)))
