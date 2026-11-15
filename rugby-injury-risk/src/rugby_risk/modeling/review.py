"""Model review report `reports/model_review_<version>.md` (F22, docs/06 §3.3, §5, §6).

Runs the production candidate (M2) and its references (M0, M1, M1w) through the single training
entry point (`run_experiment`: season folds only), then the mandatory sensitivity analyses of
docs/06 §3.3, and writes one Markdown report with the rejection criteria of §6 ticked. The
promotion box is left unticked: promotion is a human decision (docs/06 §5).

Sensitivities that the ML export cannot support are listed with their reason instead of being
silently skipped (confidence threshold 0.5: episodes under 0.6 are not materialised; injury
type: no concussion flag per episode in `ml_player_match`).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import numpy as np
import polars as pl

from rugby_risk.modeling.base import RiskModel
from rugby_risk.modeling.metrics import AUC_LEAK_ALERT, CALIBRATION_SLOPE_RANGE
from rugby_risk.modeling.runner import ExperimentConfig, ExperimentResult, run_experiment

COVID_SEASONS: Final = frozenset({"2019-2020", "2020-2021"})
STRICT_CONFIDENCE: Final = 0.8
TARGET: Final = "y_injury"
BASELINES: Final = ("m0_position", "m1_hazard_cloglog", "m1w_hazard_ipw")

Variant = Callable[[pl.DataFrame], pl.DataFrame]


@dataclass(frozen=True)
class Sensitivity:
    """One docs/06 §3.3 analysis: a data variant and/or another model, or a reason it can't run."""

    label: str
    model: str | None = None  # None = main model
    variant: Variant | None = None
    infeasible: str | None = None


def _strict_confidence(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        (pl.col(TARGET) & (pl.col("y_injury_conf").fill_null(0.0) >= STRICT_CONFIDENCE)).alias(
            TARGET
        )
    )


def _any_7d(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(pl.col("y_injury_any_7d").alias(TARGET))


def _no_covid(df: pl.DataFrame) -> pl.DataFrame:
    return df.filter(~pl.col("season_id").is_in(list(COVID_SEASONS)))


def sensitivities(df: pl.DataFrame, main: str) -> list[Sensitivity]:
    """The five docs/06 §3.3 analyses, adapted to what the export contains."""
    has_covid = bool(set(df["season_id"].unique().to_list()) & COVID_SEASONS)
    conf_raw = df["y_injury_conf"].max() if "y_injury_conf" in df.columns else None
    conf_num = conf_raw if isinstance(conf_raw, float | int) else None
    conf_max: float | None = float(conf_num) if conf_num is not None else None
    # L'export ne matérialise que les épisodes >= 0.6 : un seuil strict au-delà de la
    # confiance max disponible ne laisse aucun événement (taux global nul, journal F22).
    strict_ok = conf_max is not None and conf_max >= STRICT_CONFIDENCE
    return [
        Sensitivity(
            "Seuil de confiance 0,5",
            infeasible="épisodes < 0,6 non matérialisés dans l'export (relancer dbt avec"
            " injury_conf_threshold=0.5)",
        ),
        Sensitivity(
            f"Seuil de confiance {STRICT_CONFIDENCE}",
            variant=_strict_confidence if strict_ok else None,
            infeasible=None
            if strict_ok
            else f"confiance max {conf_max} < {STRICT_CONFIDENCE} dans l'export (relancer"
            f" dbt avec injury_conf_threshold={STRICT_CONFIDENCE})",
        ),
        Sensitivity("Cible y_injury_any_7d", variant=_any_7d),
        Sensitivity("Sans IPW", model=f"{main}_noipw"),
        Sensitivity(
            "Sans commotions",
            infeasible="type de blessure (commotion) non disponible par épisode dans"
            " ml_player_match (docs/10)",
        ),
        Sensitivity(
            "Exclusion des saisons COVID",
            variant=_no_covid if has_covid else None,
            infeasible=None if has_covid else "aucune saison COVID dans les données",
        ),
    ]


@dataclass
class Review:
    main: ExperimentResult
    baselines: dict[str, ExperimentResult] = field(default_factory=dict)
    sensitivities: list[tuple[Sensitivity, ExperimentResult | None]] = field(default_factory=list)


def run_review(
    df: pl.DataFrame,
    config: ExperimentConfig,
    factories: dict[str, Callable[[], RiskModel]],
    *,
    main: str = "m2_hierarchical",
    baselines: tuple[str, ...] = BASELINES,
) -> Review:
    """Every model goes through `run_experiment` (season folds, MLflow, experiment report).

    Sensibilités docs/06 §3.3 toujours incluses ; celles marquées infaisables sont listées
    sans ré-entraînement.
    """
    review = Review(main=run_experiment(factories[main], df, config))
    for name in baselines:
        review.baselines[name] = run_experiment(factories[name], df, config)
    for sens in sensitivities(df, main):
        if sens.infeasible:
            review.sensitivities.append((sens, None))
            continue
        data = sens.variant(df) if sens.variant else df
        factory = factories[sens.model or main]
        review.sensitivities.append((sens, run_experiment(factory, data, config)))
    return review


def _fold_lines(review: Review) -> list[str]:
    results = {review.main.model_name: review.main, **review.baselines}
    lines = [
        "| Modèle | Fold | Test | Log-loss | Brier | Brier skill | PR-AUC | ROC AUC | Pente |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name, res in results.items():
        for fr in res.folds:
            m = fr.metrics
            skill = f"{m.brier_skill:+.4f}" if m.brier_skill is not None else "n/a"
            lines.append(
                f"| {name} | {fr.fold.fold_id} | {fr.fold.test_season} | {m.log_loss:.4f}"
                f" | {m.brier:.5f} | {skill} | {m.auc_pr:.4f} | {m.auc_roc:.3f}"
                f" | {m.calibration_slope:.3f} |"
            )
    return lines


def _criteria(review: Review) -> list[tuple[str, bool, str]]:
    """docs/06 §6 rejection criteria (+ prior check) for the main model."""
    main = review.main
    skills = [fr.metrics.brier_skill or 0.0 for fr in main.folds]
    mean_skill = float(np.mean(skills)) if skills else 0.0
    lo, hi = CALIBRATION_SLOPE_RANGE
    groups = main.extra.get("group_calibration", [])
    bad_groups = [g["position_group"] for g in groups if not lo <= float(g["slope"]) <= hi]
    auc = main.aggregated.auc_roc
    params = main.extra.get("params", {})
    status = main.extra.get("run_status", "ok")
    return [
        ("Brier skill score > 0 (moyenne des folds)", mean_skill > 0, f"{mean_skill:+.4f}"),
        (
            f"Pente de calibration dans [{lo}; {hi}] pour chaque groupe de postes",
            not bad_groups,
            f"hors bornes : {', '.join(map(str, bad_groups)) or 'aucun'}",
        ),
        (
            f"ROC AUC ≤ {AUC_LEAK_ALERT} (sinon fuite à expliquer)",
            auc <= AUC_LEAK_ALERT,
            f"{auc:.3f}",
        ),
        (
            "Diagnostics MCMC : R-hat ≤ 1,01, ESS bulk/tail ≥ 400, 0 divergence",
            status == "ok",
            f"R-hat {params.get('r_hat_max')}, ESS {params.get('ess_bulk_min')}"
            f" / {params.get('ess_tail_min')}, divergences {params.get('divergences')}",
        ),
        (
            "Prior predictive check : incidence par poste dans 30-150 / 1000 h",
            bool(params.get("prior_check_ok")),
            str(params.get("prior_check_ok")),
        ),
    ]


def _sensitivity_lines(review: Review) -> list[str]:
    base = review.main.aggregated
    lines = [
        "| Analyse | Statut | Lignes | Prévalence | Log-loss | Brier skill | Pente | Rapport |",
        "|---|---|---|---|---|---|---|---|",
        f"| Référence ({review.main.model_name}) | réalisée | {base.n} | {base.prevalence:.4f}"
        f" | {base.log_loss:.4f} | {base.brier_skill if base.brier_skill is not None else 'n/a'}"
        f" | {base.calibration_slope:.3f} | `{review.main.report_path.name}` |",
    ]
    for sens, res in review.sensitivities:
        if res is None:
            lines.append(f"| {sens.label} | non réalisable : {sens.infeasible} | | | | | | |")
            continue
        a = res.aggregated
        skill = f"{a.brier_skill:+.4f}" if a.brier_skill is not None else "n/a"
        lines.append(
            f"| {sens.label} | réalisée ({res.extra.get('run_status', 'ok')}) | {a.n}"
            f" | {a.prevalence:.4f} | {a.log_loss:.4f} | {skill} | {a.calibration_slope:.3f}"
            f" | `{res.report_path.name}` |"
        )
    lines.append(
        "\nLes log-loss ne se comparent qu'à cible identique : les variantes de cible"
        " (seuil 0,8, any_7d) changent la prévalence."
    )
    return lines


def review_markdown(review: Review) -> str:
    main = review.main
    criteria = _criteria(review)
    tables = main.extra.get("tables", {})
    keep = [t for t in tables if t.startswith(("M2 :", "Courbes h(N)", "Risque cumulé"))]
    lines = [
        f"# Revue du modèle {main.run_id}",
        "",
        "Association statistique, non causale. Agrégats uniquement — aucune donnée nominative.",
        "",
        f"- Modèle candidat : `{main.model_name}` (statut `{main.extra.get('run_status', 'ok')}`)",
        f"- dataset_version : `{main.dataset_version}`",
        f"- git_sha : `{main.git_sha}`",
        f"- Rapport d'expérience : `reports/experiments/{main.report_path.name}`",
        f"- Artefacts : {', '.join(f'`{a}`' for a in main.extra.get('artifacts', [])) or '-'}",
        "",
        "## Critères de rejet (docs/06 §6)",
        "",
        *[f"- [{'x' if ok else ' '}] {label} : {detail}" for label, ok, detail in criteria],
        "",
        "## Métriques par fold vs M0 / M1 / M1w",
        "",
        *_fold_lines(review),
        "",
        "## Calibration par groupe de postes",
        "",
        "Voir le rapport d'expérience (section « Calibration par groupe de postes »).",
        "",
        "| Groupe | Blessures | Observé | Prédit | Pente |",
        "|---|---|---|---|---|",
        *[
            f"| {g['position_group']} | {g['events']} | {g['observed']:.4f}"
            f" | {g['predicted']:.4f} | {g['slope']:.3f} |"
            for g in main.extra.get("group_calibration", [])
        ],
        "",
    ]
    for title in keep:
        lines += [f"## {title}", "", tables[title], ""]
    lines += [
        "## Sensibilités (docs/06 §3.3)",
        "",
        *_sensitivity_lines(review),
        "",
        "## Décision",
        "",
        "- [ ] Promotion en production (décision humaine, après lecture de ce rapport).",
        "",
        "Version enregistrée dans le registre MLflow `rugby-risk-m2` sans promotion.",
        "",
    ]
    return "\n".join(lines)


def write_review(review: Review, directory: Path = Path("reports")) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"model_review_{review.main.run_id}.md"
    path.write_text(review_markdown(review), encoding="utf-8")
    return path
