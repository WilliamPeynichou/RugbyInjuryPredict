"""Experiment runner (F18): rolling-origin folds -> metrics -> MLflow -> Markdown report.

Every model (F19+) goes through `run_experiment`; this is the only training entry point, which
makes random k-fold structurally impossible (folds come from `season_folds` only).
"""

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from rugby_risk.modeling.base import RiskModel
from rugby_risk.modeling.baselines import GlobalRateModel
from rugby_risk.modeling.bootstrap import cluster_bootstrap, percentile_interval
from rugby_risk.modeling.metrics import Metrics, calibration_curve, evaluate
from rugby_risk.modeling.report import experiment_markdown
from rugby_risk.modeling.validation import Fold, season_folds


@dataclass(frozen=True)
class ExperimentConfig:
    """Protocol knobs, logged to MLflow. Dataset identity comes from tags, not here."""

    min_train_seasons: int = 5
    allow_final_test: bool = False
    bootstrap_replications: int = 500
    seed: int = 0
    target_col: str = "y_injury"
    mlflow_uri: str = "sqlite:///data/mlflow.db"  # file store déprécié mlflow 3.x


@dataclass(frozen=True)
class FoldResult:
    """Out-of-sample predictions and metrics for one fold."""

    fold: Fold
    metrics: Metrics
    brier_boot_low: float
    brier_boot_high: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "fold": self.fold.fold_id,
            "test_season": self.fold.test_season,
            **self.metrics.as_dict(),
        }


@dataclass(frozen=True)
class ExperimentResult:
    """What `run_experiment` returns and what the report is built from."""

    run_id: str
    model_name: str
    dataset_version: str
    git_sha: str | None
    folds: tuple[FoldResult, ...]
    aggregated: Metrics
    brier_boot_low: float
    brier_boot_high: float
    report_path: Path
    config: ExperimentConfig
    extra: dict[str, Any] = field(default_factory=dict)


def git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False, timeout=10
        )
        return out.stdout.strip() or None
    except OSError:
        return None


def _played(df: pl.DataFrame, seasons: tuple[str, ...], config: ExperimentConfig) -> pl.DataFrame:
    # Les lignes jouées sans minutes connues (trou de parsing, S7) sont exclues :
    # l'exposition est l'offset du hazard, sans elle pas de prédiction honnête.
    # Sur les vraies données ces lignes ont toutes y_injury = 0 (0,8 % des jouées).
    return (
        df.filter(pl.col("season_id").is_in(list(seasons)))
        .filter(pl.col("played"))
        .drop_nulls(subset=[config.target_col, "minutes_played"])
    )


def _calibration_figure(curve: dict[str, np.ndarray], title: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], "k--", linewidth=1, label="parfait")
    ax.plot(curve["p_pred"], curve["p_obs"], "o-", label="observé")
    ax.set_xlabel("probabilité prédite")
    ax.set_ylabel("fréquence observée")
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def run_experiment(
    model_factory: Callable[[], RiskModel],
    df: pl.DataFrame,
    config: ExperimentConfig | None = None,
) -> ExperimentResult:
    """Train and evaluate a model across rolling-origin seasons.

    `df` is the full `ml_player_match` export. Only played rows are used: selection is a
    separate sub-problem (F21). No column identifying a player ever leaves this function.
    """
    config = config or ExperimentConfig()
    model = model_factory()
    seasons = sorted(df["season_id"].unique().to_list())
    folds = season_folds(seasons, min_train_seasons=config.min_train_seasons)
    if not folds:
        raise ValueError(
            f"Pas assez de saisons ({len(seasons)}) pour"
            f" min_train_seasons={config.min_train_seasons}"
        )
    dataset_version = str(df["dataset_version"][0])
    sha = git_sha()
    fold_results: list[FoldResult] = []
    pooled_y: list[np.ndarray] = []
    pooled_p: list[np.ndarray] = []
    pooled_ref: list[np.ndarray] = []
    for fold in folds:
        train = _played(df, fold.train_seasons, config)
        valid = _played(df, (fold.valid_season,), config)
        test = _played(df, (fold.test_season,), config)
        model = model_factory().fit(train, valid)
        p = np.clip(model.predict_proba(test), 1e-6, 1 - 1e-6)
        y = test[config.target_col].to_numpy().astype(float)
        metrics = evaluate(y, p)
        # Référence M0 (taux global) : Brier skill score vs elle (docs/06 §3.2).
        ref_model = GlobalRateModel(target_col=config.target_col).fit(train)
        ref = np.clip(ref_model.predict_proba(test), 1e-6, 1 - 1e-6)
        pooled_ref.append(ref)

        def brier_on(mask: np.ndarray, y: np.ndarray = y, p: np.ndarray = p) -> float:
            return float(evaluate(y[mask], p[mask]).brier)

        boot = cluster_bootstrap(
            test["player_key"].to_numpy(),
            brier_on,
            replications=config.bootstrap_replications,
            seed=config.seed,
        )
        lo, hi = percentile_interval(boot)
        fold_results.append(
            FoldResult(fold=fold, metrics=metrics, brier_boot_low=lo, brier_boot_high=hi)
        )
        pooled_y.append(y)
        pooled_p.append(p)
    y_all = np.concatenate(pooled_y)
    p_all = np.concatenate(pooled_p)
    aggregated = evaluate(y_all, p_all, p_reference=np.concatenate(pooled_ref))
    pooled_keys = np.concatenate(
        [
            _played(df, (fr.fold.test_season,), config)["player_key"].to_numpy()
            for fr in fold_results
        ]
    )

    def brier_pooled(mask: np.ndarray, y: np.ndarray = y_all, p: np.ndarray = p_all) -> float:
        return float(evaluate(y[mask], p[mask]).brier)

    boot_pooled = cluster_bootstrap(
        pooled_keys,
        brier_pooled,
        replications=config.bootstrap_replications,
        seed=config.seed,
    )
    brier_lo, brier_hi = percentile_interval(boot_pooled)

    run_id = f"{model.name}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    reports = Path("reports") / "experiments"
    reports.mkdir(parents=True, exist_ok=True)
    curve = calibration_curve(y_all, p_all)
    fig_path = reports / f"{run_id}_calibration.png"
    _calibration_figure(curve, f"{model.name} - calibration pooled", fig_path)
    result = ExperimentResult(
        run_id=run_id,
        model_name=model.name,
        dataset_version=dataset_version,
        git_sha=sha,
        folds=tuple(fold_results),
        aggregated=aggregated,
        brier_boot_low=brier_lo,
        brier_boot_high=brier_hi,
        report_path=reports / f"{run_id}.md",
        config=config,
        extra={
            "params": model.params(),
            "tables": getattr(model, "report_tables", lambda: {})() or {},
        },
    )
    result.report_path.write_text(experiment_markdown(result), encoding="utf-8")
    _log_mlflow(result, curve, fig_path)
    return result


def _log_mlflow(result: ExperimentResult, curve: dict[str, np.ndarray], fig_path: Path) -> None:
    """Best-effort MLflow logging; a tracking server failure must not lose the report."""
    import mlflow  # noqa: PLC0415 - import paresseux : MLflow n'est requis qu'au logging

    mlflow.set_tracking_uri(result.config.mlflow_uri)
    with mlflow.start_run(run_name=result.run_id):
        mlflow.log_params(
            {
                "model": result.model_name,
                "min_train_seasons": result.config.min_train_seasons,
                "bootstrap_replications": result.config.bootstrap_replications,
                "seed": result.config.seed,
                "target_col": result.config.target_col,
                **{f"model_{k}": v for k, v in result.extra["params"].items()},
            }
        )
        mlflow.set_tags(
            {
                "dataset_version": result.dataset_version,
                "git_sha": result.git_sha or "",
                "allow_final_test": str(result.config.allow_final_test),
            }
        )
        for name, value in result.aggregated.as_dict().items():
            if isinstance(value, (int, float)) and not np.isnan(value):
                mlflow.log_metric(f"test_{name}", value)
        mlflow.log_metrics(
            {
                "test_brier_boot_low": result.brier_boot_low,
                "test_brier_boot_high": result.brier_boot_high,
            }
        )
        for fr in result.folds:
            for name, value in fr.metrics.as_dict().items():
                if isinstance(value, (int, float)) and not np.isnan(value):
                    mlflow.log_metric(f"fold{fr.fold.fold_id}_{name}", value)
        mlflow.log_artifact(str(fig_path))
        mlflow.log_artifact(str(result.report_path))
