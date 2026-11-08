"""Markdown report for one experiment (F18). Aggregates only: never a player_key."""

from typing import TYPE_CHECKING

from rugby_risk.modeling.metrics import CALIBRATION_SLOPE_RANGE

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
        f"- Labels censurés exclus (suivi < {result.extra.get('min_label_followup')} matchs"
        f" dans la saison) : {result.extra.get('censored_played_rows', 0)} lignes jouées",
        f"- Splits : rolling origin, min_train_seasons={result.config.min_train_seasons},"
        f" test final autorisé : {result.config.allow_final_test}",
        f"- Statut du run : `{result.extra.get('run_status', 'ok')}`",
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
        "| Fold | Test | Lignes | Prévalence | Log-loss | Brier | Brier skill"
        " | Brier IC90 | PR-AUC |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for fr in result.folds:
        m = fr.metrics
        skill = f"{m.brier_skill:.4f}" if m.brier_skill is not None else "n/a"
        lines.append(
            f"| {fr.fold.fold_id} | {fr.fold.test_season} | {m.n} | {m.prevalence:.4f}"
            f" | {m.log_loss:.4f} | {m.brier:.5f} | {skill}"
            f" | [{fr.brier_boot_low:.5f}; {fr.brier_boot_high:.5f}] | {m.auc_pr:.4f} |"
        )
    if agg.alerts:
        lines += ["", "## Alertes", ""]
        lines += [f"- {a}" for a in agg.alerts]
    groups = result.extra.get("group_calibration", [])
    if groups:
        lines += [
            "",
            "## Calibration par groupe de postes (pooled test)",
            "",
            "| Groupe | Lignes | Blessures | Observé | Prédit | Pente | Intercept | Pente OK |",
            "|---|---|---|---|---|---|---|---|",
        ]
        lo, hi = CALIBRATION_SLOPE_RANGE
        lines += [
            f"| {g['position_group']} | {g['n']} | {g['events']} | {g['observed']:.4f}"
            f" | {g['predicted']:.4f} | {g['slope']:.3f} | {g['intercept']:.3f}"
            f" | {lo <= float(g['slope']) <= hi} |"
            for g in groups
        ]
        lines.append(
            f"\nCritère docs/06 §6 : pente dans [{lo}; {hi}] pour chaque groupe. Peu d'événements"
            " par groupe : pente très bruitée, à lire avec le nombre de blessures."
        )
    tables = result.extra.get("tables", {})
    if tables:
        lines.append("")
        for title, body in tables.items():
            lines += [f"## {title}", "", body, ""]
    lines += [
        "",
        "Figures : "
        + ", ".join(
            f"`reports/experiments/{name}`"
            for name in result.extra.get("figures", [f"{result.run_id}_calibration.png"])
        )
        + ".",
        "",
    ]
    return "\n".join(lines)
