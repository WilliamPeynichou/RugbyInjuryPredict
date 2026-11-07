"""F17 asset: export the pseudonymised ML table built by dbt (`ml_player_match`)."""

from contextlib import closing
from pathlib import Path

from dagster import AssetExecutionContext, Output, asset

from orchestration.assets.entities import warehouse_lock
from orchestration.assets.injuries import injury_episodes
from rugby_risk.features.export import export, profile_markdown
from rugby_risk.settings import get_settings
from rugby_risk.warehouse import connect


@asset(deps=[injury_episodes], compute_kind="python")
def ml_table(context: AssetExecutionContext) -> Output:
    """dbt already built `ml_player_match` (injury_episodes runs the full build): export it."""
    with warehouse_lock(), closing(connect()) as con:
        path, version = export(con, get_settings().data_dir / "ml")
        rows = con.execute("select count(*) from ml_player_match").fetchone()
        report = profile_markdown(con)
    reports = Path("reports")
    reports.mkdir(exist_ok=True)
    (reports / "ml_table_profile.md").write_text(report, encoding="utf-8")
    context.log.info("ml_player_match: %s lignes, version %s", rows[0] if rows else 0, version)
    return Output(
        None,
        metadata={"rows": rows[0] if rows else 0, "dataset_version": version, "path": str(path)},
    )
