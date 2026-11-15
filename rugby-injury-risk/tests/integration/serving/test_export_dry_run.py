"""F25 export: dry-run idempotent, guard re-applied at the sink, Supabase upsert mocked."""

import re
from pathlib import Path

import httpx
import polars as pl
import pytest
import respx

from rugby_risk.errors import PrivacyViolationError
from rugby_risk.serving.batch import TABLES, PublicTables
from rugby_risk.serving.export import (
    CONFLICT_KEYS,
    DryRunSink,
    PublishTransportError,
    SupabaseSink,
    publish,
)

pytestmark = pytest.mark.integration


def _tables() -> PublicTables:
    rows = pl.DataFrame(
        {
            "model_version": ["m2_test"],
            "season_id": ["s"],
            "position_code": ["PROP"],
            "n_consecutive": [0],
            "scenario": ["median"],
            "p_mean": [0.02],
            "p_low90": [0.01],
            "p_high90": [0.03],
            "cum_mean": [0.02],
            "cum_low90": [0.01],
            "cum_high90": [0.03],
            "n_players_support": [50],
            "computed_at": ["t"],
        }
    )
    registry = pl.DataFrame([{"model_version": "m2_test", "promoted": False}])
    return PublicTables(
        model_version="m2_test",
        dataset_version="ds",
        promoted=False,
        computed_at="t",
        tables={
            "pred_position_curve": rows,
            "pred_position_season": rows.drop("n_consecutive", "scenario", "p_low90", "p_high90"),
            "calibration_public": rows.select(
                ["model_version", "p_mean", "p_low90", "n_players_support"]
            )
            .rename({"p_mean": "p_pred_mean", "p_low90": "p_obs"})
            .with_columns(
                pl.lit("all").alias("position_group"),
                pl.lit("2024-2025").alias("test_season"),
                pl.lit(0).alias("bin"),
                pl.lit(100).alias("n"),
            ),
            "model_registry_public": registry,
        },
    )


def test_publish_dry_run_is_idempotent(tmp_path) -> None:
    sink = DryRunSink(directory=tmp_path)
    publish(_tables(), sink)
    first = {p.name: p.read_text(encoding="utf-8") for p in tmp_path.glob("*.csv")}
    assert {p.stem for p in tmp_path.glob("*.csv")} == set(TABLES)
    publish(_tables(), sink)  # deuxième run : fichiers inchangés
    second = {p.name: p.read_text(encoding="utf-8") for p in tmp_path.glob("*.csv")}
    assert first == second


def test_publish_rechecks_the_guard(tmp_path) -> None:
    public = _tables()
    leaked = public.tables["pred_position_curve"].with_columns(pl.lit("x").alias("player_key"))
    public.tables["pred_position_curve"] = leaked
    with pytest.raises(PrivacyViolationError):
        publish(public, DryRunSink(directory=tmp_path))


def test_publish_requires_all_tables(tmp_path) -> None:
    public = _tables()
    del public.tables["calibration_public"]
    with pytest.raises(PrivacyViolationError):
        publish(public, DryRunSink(directory=tmp_path))


@respx.mock
def test_supabase_sink_upsert_on_conflict_matches_primary_key() -> None:
    route = respx.post("https://example.supabase.co/rest/v1/pred_position_curve").mock(
        return_value=httpx.Response(201)
    )
    SupabaseSink("https://example.supabase.co", "key").write(
        "pred_position_curve", _tables().tables["pred_position_curve"]
    )
    assert route.called
    sent = route.calls.last.request
    assert sent.url.params["on_conflict"] == ",".join(CONFLICT_KEYS["pred_position_curve"])
    assert sent.headers["Prefer"] == "resolution=merge-duplicates"


def test_conflict_keys_match_sql_primary_keys() -> None:
    sql = Path("supabase/migrations/0001_public_tables.sql").read_text(encoding="utf-8")
    for table, keys in CONFLICT_KEYS.items():
        block = sql[sql.index(f"create table if not exists public.{table} (") :]
        block = block[: block.index(");")]
        primary = re.search(r"primary key \(([^)]*)\)", block)
        if primary is None:  # clé primaire déclarée sur la colonne (model_registry_public)
            primary = re.search(r"(\w+)\s+text\s+primary key", block)
            declared = (primary.group(1),) if primary else ()
        else:
            declared = tuple(c.strip() for c in primary.group(1).split(","))
        assert declared == keys, table


@respx.mock
def test_supabase_sink_refuses_http_error() -> None:
    respx.post("https://example.supabase.co/rest/v1/pred_position_curve").mock(
        return_value=__import__("httpx").Response(400)
    )
    with pytest.raises(PublishTransportError):
        SupabaseSink("https://example.supabase.co", "key").write(
            "pred_position_curve", _tables().tables["pred_position_curve"]
        )
