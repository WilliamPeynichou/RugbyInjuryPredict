"""Markdown report for one experiment (F18). Aggregates only: never a player_key."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rugby_risk.modeling.runner import ExperimentResult


def experiment_markdown(result: "ExperimentResult") -> str:
    """Aggregated experiment report (docs/06 §5). Read with the calibration figure."""
    agg = result.aggregated
    lines = [
        f"# Expérience {result.run_id}",
        "",
        "Association statistique, non causale. Agrégats uniquement — aucune donnée nominative.",
        "",
        f"- Modèle : `{result.model_name}`",
        f"- dataset_version : `{result.dataset_version}`",
        f"- git_sha : `{result.git_sha}`",
        f"- Cible : `{result.config.target_col}` (lignes jouées uniquement)",
        f"- Splits : rolling origin, min_train_seasons={result.config.min_train_seasons},"
        f" test final autorisé : {result.config.allow_final_test}",
        "",
        "## Résultat agrégé (pooled sur les saisons de test)",
        "",
        "| Métrique | Valeur |",
        "|---|---|",
        f"| Lignes | {agg.n} |",
        f"| Prévalence observée | {agg.prevalence:.4f} |",
        f"| Incidence prédite | {agg.predicted_incidence:.4f} |",
        f"| Log-loss | {agg.log_loss:.4f} |",
        f"| Brier | {agg.brier:.5f} |",
        "| Brier skill (vs référence) |"
        f" {agg.brier_skill if agg.brier_skill is not None else 'n/a'} |",
        "| Brier IC90 bootstrap joueur |"
        f" [{result.brier_boot_low:.5f}; {result.brier_boot_high:.5f}] |",
        f"| PR-AUC | {agg.auc_pr:.4f} |",
        f"| ROC AUC | {agg.auc_roc:.4f} |",
        f"| Pente de calibration | {agg.calibration_slope:.3f} |",
        f"| Intercept de calibration | {agg.calibration_intercept:.3f} |",
        "",
        "## Folds",
        "",
        "| Fold | Test | Lignes | Prévalence | Log-loss | Brier | Brier IC90 | PR-AUC |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for fr in result.folds:
        m = fr.metrics
        lines.append(
            f"| {fr.fold.fold_id} | {fr.fold.test_season} | {m.n} | {m.prevalence:.4f}"
            f" | {m.log_loss:.4f} | {m.brier:.5f}"
            f" | [{fr.brier_boot_low:.5f}; {fr.brier_boot_high:.5f}] | {m.auc_pr:.4f} |"
        )
    if agg.alerts:
        lines += ["", "## Alertes", ""]
        lines += [f"- {a}" for a in agg.alerts]
    lines += [
        "",
        f"Figure : `reports/experiments/{result.run_id}_calibration.png`.",
        "",
    ]
    return "\n".join(lines)
