"""F16 asset: fuse injury signals into `fact_injury_event` (offline, idempotent)."""

import csv
import json
from contextlib import closing
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
from dbt.cli.main import dbtRunner

from orchestration.assets.dbt_assets import participation_marts
from orchestration.assets.entities import warehouse_lock
from orchestration.assets.injury_mentions import injury_mentions
from rugby_risk.injuries import priors
from rugby_risk.injuries.fusion import episode_frame, fuse
from rugby_risk.injuries.fusion_inputs import (
    absence_signals,
    announcement_signals,
    exit_signals,
    first_returns_after,
)
from rugby_risk.injuries.rules import dbt_vars, load_rules
from rugby_risk.marts import build_marts
from rugby_risk.settings import get_settings
from rugby_risk.warehouse import connect, write_staging


def _table(con: duckdb.DuckDBPyConnection, name: str) -> pl.DataFrame:
    arrow = con.execute(f"select * from {name}").to_arrow_table()
    return cast(pl.DataFrame, pl.from_arrow(arrow))


def _opt_out_ids() -> set[int]:
    path = Path("data/reference/opt_out.csv")
    if not path.exists():
        return set()
    with path.open(encoding="utf-8") as fh:
        return {int(row["player_id"]) for row in csv.DictReader(fh) if row.get("player_id")}


@asset(deps=[participation_marts, injury_mentions], compute_kind="python")
def injury_episodes(context: AssetExecutionContext) -> Output:
    """Read exit/absence/announcement signals, fuse, stage `injury_episode`, dbt build."""
    rules = load_rules().fusion
    with warehouse_lock(), closing(connect()) as con:
        matches = _table(con, "fact_match").select(
            "match_id",
            "kickoff_ts",
            pl.col("kickoff_ts").dt.convert_time_zone("UTC").dt.date().alias("match_date"),
        )
        exits = _table(con, "int_injury_signal__exit").join(
            matches.select("match_id", "match_date"), on="match_id"
        )
        runs = _table(con, "int_absence_runs").filter(
            pl.col("absence_reason") == "injury_candidate"
        )
        eligibility = _table(con, "fact_eligibility").join(matches, on="match_id")
        returns = first_returns_after(eligibility, runs)
        signals = (
            exit_signals(exits) + absence_signals(runs, returns) + announcement_signals(_mentions())
        )
        episodes = fuse(signals, rules, opt_out=_opt_out_ids())
        write_staging(episode_frame(episodes), "injury_episode", "fusion", "all")
        data_dir = get_settings().data_dir
        ok = build_marts(data_dir / "staging", data_dir / "dbt_logs", data_dir / "dbt_target")
        if not ok:
            raise RuntimeError("dbt build en échec après fusion (voir data/dbt_logs)")
        incidence = priors.incidence_rows(con)
    reports = Path("reports")
    reports.mkdir(exist_ok=True)
    (reports / "injury_incidence.md").write_text(
        priors.incidence_markdown(incidence), encoding="utf-8"
    )
    counts = {
        k: sum(1 for e in episodes if k in e.signals) for k in ("exit", "absence", "announcement")
    }
    context.log.info(
        "Épisodes: %d (exit=%d absence=%d annonce=%d)", len(episodes), *counts.values()
    )
    return Output(
        None,
        metadata={"episodes": len(episodes), **{f"with_{k}": v for k, v in counts.items()}},
    )


def _read_staging(entity: str) -> pl.DataFrame | None:
    paths = sorted(get_settings().data_dir.glob(f"staging/{entity}/**/part.parquet"))
    return pl.concat([pl.read_parquet(p) for p in paths]) if paths else None


def _mentions() -> pl.DataFrame:
    """Press mentions from the staging lake (F15 writes parquet; no dbt model yet)."""
    mentions = _read_staging("injury_mention")
    if mentions is None:
        return pl.DataFrame(
            schema={
                "mention_id": pl.String,
                "doc_id": pl.String,
                "player_id": pl.Int64,
                "match_id": pl.Int64,
                "onset_date": pl.Date,
                "onset_context": pl.String,
                "body_region": pl.String,
                "injury_type": pl.String,
                "is_concussion": pl.Boolean,
                "announced_duration_days_min": pl.Int64,
                "announced_duration_days_max": pl.Int64,
                "quote": pl.String,
                "published_at": pl.Datetime("us", "UTC"),
                "doc_url": pl.String,
            }
        )
    linked = mentions.filter(pl.col("player_id").is_not_null())
    docs = _read_staging("news_doc")
    if docs is None:
        return linked.with_columns(pl.lit(None).alias("doc_url"))
    doc_cols = docs.select(["doc_id", "url"]).rename({"url": "doc_url"})
    return linked.join(doc_cols, on="doc_id", how="left")


def dbt_test_injury_models() -> bool:
    """Run only the fact_injury_event model + its tests (used by tests/integration)."""
    result = dbtRunner().invoke(
        [
            "build",
            "--project-dir",
            "dbt",
            "--profiles-dir",
            "dbt",
            "--select",
            "fact_injury_event",
            "--vars",
            json.dumps(dbt_vars()),
        ]
    )
    return bool(result.success)


@asset_check(asset=injury_episodes)
def injury_incidence_prior_check() -> AssetCheckResult:
    """WARN quand l'incidence reconstruite sort de la plage docs/02 (40-110 / 1000 h)."""
    with warehouse_lock(), closing(connect()) as con:
        outside = priors.prior_violations(priors.incidence_rows(con))
    return AssetCheckResult(
        passed=True,  # jamais bloquant : c'est un signal de qualité des étiquettes
        severity=AssetCheckSeverity.WARN,
        metadata={
            "hors_plage": len(outside),
            "detail": ", ".join(f"{r.season}/{r.position_group}" for r in outside) or "-",
        },
    )
