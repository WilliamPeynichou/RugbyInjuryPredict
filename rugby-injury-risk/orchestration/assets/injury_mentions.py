"""F15 asset: LLM injury-mention extraction from staged press documents (offline)."""

from contextlib import closing
from pathlib import Path
from typing import cast

import polars as pl
from dagster import AssetExecutionContext, Output, asset

from orchestration.assets.entities import warehouse_lock
from rugby_risk.injuries.extract import run_extraction, usage_report
from rugby_risk.injuries.llm_client import LlmUsage, extract_json
from rugby_risk.settings import get_settings
from rugby_risk.warehouse import connect, write_staging


# data/staging/news_doc n'existe que si F14 a tourné (source presse autorisée) ; sinon no-op.
def _documents(staging: Path) -> pl.DataFrame | None:
    paths = sorted(staging.glob("news_doc/**/part.parquet"))
    if not paths:
        return None
    return pl.concat([pl.read_parquet(p) for p in paths], how="vertical_relaxed")


@asset(deps=[], compute_kind="python")
def injury_mentions(context: AssetExecutionContext) -> Output:
    """Extract structured injury mentions from staged press docs into `injury_mention`."""
    staging = get_settings().data_dir / "staging"
    documents = _documents(staging)
    if documents is None:
        return Output(None, metadata={"documents": 0, "mentions": 0, "skipped": True})
    with warehouse_lock(), closing(connect()) as con:

        def table(name: str) -> pl.DataFrame:
            arrow = con.execute(f"select * from {name}").to_arrow_table()
            return cast(pl.DataFrame, pl.from_arrow(arrow))

        dim_player = table("dim_player")
        squad = table("fact_squad_membership")
        teams = table("dim_team")
        matches = table("fact_match")
        usage = LlmUsage()
        frame = run_extraction(
            documents, dim_player, squad, teams, matches, extract_json, usage=usage
        )
        write_staging(frame, "injury_mention", "llm", "all")
        report_dir = staging / "_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "llm_usage.md").write_text(usage_report(usage), encoding="utf-8")
    context.log.info("Extraction: %d docs, %d mentions", len(documents), frame.height)
    return Output(
        None,
        metadata={
            "documents": len(documents),
            "mentions": frame.height,
            "review": int(frame["needs_review"].sum()),
            "prompt_tokens": usage.prompt_tokens,
        },
    )
