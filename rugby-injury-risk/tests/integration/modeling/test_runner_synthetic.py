"""F18 integration: full runner on synthetic F17 data, local MLflow, privacy guard."""

import time
from pathlib import Path

import duckdb
import polars as pl
import pytest

from rugby_risk.modeling.bootstrap import cluster_bootstrap, percentile_interval
from rugby_risk.modeling.null import ConstantModel
from rugby_risk.modeling.runner import ExperimentConfig, run_experiment
from tests.factories import build_ml, make_league

pytestmark = pytest.mark.integration


def _ml_frame(warehouse: Path):

    with duckdb.connect(str(warehouse)) as con:
        return pl.from_arrow(
            con.execute(
                """select season_id, played, y_injury, player_key, dataset_version, kickoff_ts,
                          minutes_played
            from ml_player_match"""
            ).to_arrow_table()
        )


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    league = make_league(seasons=3, seed=1)
    warehouse = tmp_path_factory.mktemp("runner") / "w.duckdb"
    assert build_ml(warehouse, tmp_path_factory.mktemp("dbt"), league)
    df = _ml_frame(warehouse)
    config = ExperimentConfig(
        min_train_seasons=1,
        bootstrap_replications=50,
        seed=0,
        mlflow_uri=f"sqlite:///{tmp_path_factory.mktemp('mlflow')}/mlflow.db",
        reports_dir=tmp_path_factory.mktemp("experiments"),
    )
    started = time.monotonic()
    out = run_experiment(lambda: ConstantModel(), df, config)  # noqa: PLW0108 - factory
    elapsed = time.monotonic() - started
    assert elapsed < 60, f"run trop lent: {elapsed:.1f}s"
    return out


def test_run_completes_with_expected_metrics(result) -> None:
    assert result.folds, "au moins un fold"
    assert result.aggregated.n > 0
    assert result.aggregated.log_loss > 0
    assert result.aggregated.brier > 0
    # Prévalence pooled proche du taux injecté (0.08 +/- 2 points).
    assert abs(result.aggregated.prevalence - 0.08) < 0.02
    # Le modèle constant prédit le taux de train : incidence prédite proche de l'observée.
    assert abs(result.aggregated.predicted_incidence - result.aggregated.prevalence) < 0.02


def test_report_written_without_player_keys(result) -> None:
    text = result.report_path.read_text(encoding="utf-8")
    assert result.model_name in text and "player_key" not in text
    assert (result.report_path.parent / f"{result.run_id}_calibration.png").exists()


def test_mlflow_run_logged(tmp_path_factory, result) -> None:
    import mlflow  # noqa: PLC0415 - import paresseux volontaire

    mlflow.set_tracking_uri(result.config.mlflow_uri)
    runs = mlflow.search_runs(experiment_ids=["0"])
    assert len(runs) == 1
    run_id = runs.iloc[0]["run_id"]
    run = mlflow.get_run(run_id)
    assert run.data.tags["dataset_version"] == result.dataset_version
    assert "test_log_loss" in run.data.metrics
    artifacts = [a.path for a in mlflow.MlflowClient().list_artifacts(run_id)]
    assert any(a.endswith(".png") for a in artifacts)
    assert any(a.endswith(".md") for a in artifacts)
    # Garde-fou vie privée : aucun artefact ne contient de player_key.
    client = mlflow.MlflowClient()
    for artifact in artifacts:
        local = client.download_artifacts(
            run_id, artifact, dst_path=str(tmp_path_factory.mktemp("art"))
        )
        if local.endswith((".md", ".txt")):
            assert "player_key" not in Path(local).read_text(encoding="utf-8")


def test_cluster_bootstrap_resamples_whole_players() -> None:
    import numpy as np  # noqa: PLC0415

    keys = np.array(["a", "a", "b", "c", "c", "c"])
    scores = cluster_bootstrap(
        keys,
        lambda mask: float(mask.sum()),
        replications=20,
        seed=0,
    )
    # Chaque réplication garde tous les rows des joueurs tirés : somme multiple cohérente.
    assert all(s in {0, 2, 3, 4, 5, 6, 7, 8, 9} for s in scores)
    lo, hi = percentile_interval(scores)
    assert lo <= hi
