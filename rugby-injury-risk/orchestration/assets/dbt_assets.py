"""dbt marts asset (F10): participation marts, coverage report, Top 14 minutes quality gate.

Plain `dbtRunner` call instead of dagster-dbt: no extra dependency, one asset for the whole
dbt project. shortcut: no per-model lineage in Dagster, switch to dagster-dbt if needed (F28).
"""

from contextlib import closing
from pathlib import Path

from dagster import (
    AssetCheckResult,
    AssetCheckSeverity,
    AssetExecutionContext,
    Failure,
    Output,
    asset,
    asset_check,
)

from orchestration.assets.calendar import calendar_staging
from orchestration.assets.entities import player_entities, warehouse_lock
from rugby_risk.marts import QUALITY_THRESHOLD, build_marts, coverage_markdown, low_quality_seasons
from rugby_risk.settings import get_settings
from rugby_risk.warehouse import connect

COVERAGE_PATH = Path("reports/coverage.md")


@asset(deps=[calendar_staging, player_entities], compute_kind="dbt")
def participation_marts(context: AssetExecutionContext) -> Output:
    """`dbt build` (marts + tests), then write reports/coverage.md."""
    data_dir = get_settings().data_dir
    with warehouse_lock():
        ok = build_marts(data_dir / "staging", data_dir / "dbt_logs", data_dir / "dbt_target")
        if not ok:
            raise Failure("dbt build en échec (voir data/dbt_logs)")
        with closing(connect()) as con:
            report = coverage_markdown(con)
            low = low_quality_seasons(con)
    COVERAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    COVERAGE_PATH.write_text(report, encoding="utf-8")
    context.log.info("Saisons quality_flag=low: %s", low)
    return Output(None, metadata={"low_quality_seasons": len(low)})


@asset_check(asset=participation_marts)
def top14_minutes_quality() -> AssetCheckResult:
    with warehouse_lock(), closing(connect()) as con:
        low = low_quality_seasons(con)
    return AssetCheckResult(
        passed=not low,
        severity=AssetCheckSeverity.ERROR,
        metadata={"threshold": QUALITY_THRESHOLD, "low_seasons": ", ".join(low) or "-"},
    )
