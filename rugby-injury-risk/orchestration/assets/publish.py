"""F25 asset: publish the aggregated public tables (dry-run folder or Supabase)."""

from pathlib import Path

import polars as pl
from dagster import AssetExecutionContext, Output, asset

from orchestration.assets.ml import ml_table
from rugby_risk.modeling.artifact import is_promoted, latest_artifact
from rugby_risk.serving.batch import build_public_tables
from rugby_risk.serving.export import DryRunSink, SupabaseSink, publish
from rugby_risk.settings import get_settings


@asset(deps=[ml_table], compute_kind="python")
def public_predictions(context: AssetExecutionContext) -> Output:
    """Build the four public tables and write them where the promotion state allows."""
    directory = latest_artifact()
    public = build_public_tables(
        directory, pl.read_parquet(Path("data/ml/ml_player_match.parquet"))
    )
    settings = get_settings()
    if is_promoted(directory) and settings.supabase_url:
        publish(
            public,
            SupabaseSink(settings.supabase_url, settings.supabase_service_key.get_secret_value()),
        )
        destination = "supabase"
    else:
        publish(public, DryRunSink())
        destination = "dry-run"
    context.log.info(
        "public_predictions: modèle %s (%s) -> %s",
        public.model_version,
        "promu" if public.promoted else "non promu",
        destination,
    )
    return Output(
        None,
        metadata={
            "model_version": public.model_version,
            "promoted": public.promoted,
            "dataset_version": public.dataset_version,
            "destination": destination,
        },
    )
