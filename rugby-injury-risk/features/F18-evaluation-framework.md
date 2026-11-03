# F18 — Cadre d'évaluation temporelle et MLflow

| Champ | Valeur |
|---|---|
| Phase | 4 |
| Dépendances | F17 |
| Estimation | M |
| Docs de référence | `docs/06-modeling.md` §3, §5–6, `CLAUDE.md` règles 2 et 8 |

## Objectif

Fournir un cadre commun et unique pour entraîner, évaluer et tracer n'importe quel modèle : splits par saison, métriques de calibration, bootstrap par joueur, rapports, MLflow.

## Contexte

Tous les modèles (F19–F24) passent par ce cadre. Il rend impossible un k-fold aléatoire et garantit des comparaisons à protocole identique.

## Périmètre

- [ ] Ajouter `mlflow`, `scikit-learn`, `matplotlib`.
- [ ] `modeling/validation.py` :
  - `season_folds(df, min_train_seasons=5, test_final="2025-2026") -> list[Fold]` (rolling origin, saison de validation, exclusion des saisons COVID en test simple) ;
  - garde-fou : toute tentative d'utiliser `sklearn.model_selection.KFold`/`train_test_split` dans `src/rugby_risk/modeling/` est détectée par un test (grep) ;
  - le test final `2025-2026` n'est utilisable qu'avec `allow_final_test=True` (journalisé).
- [ ] `modeling/metrics.py` : log-loss, Brier, Brier skill score vs référence, pente et intercept de calibration, courbe de calibration (bins quantiles), PR-AUC, ROC AUC, incidence prédite vs observée par groupe ; alerte `AUC > 0.75`.
- [ ] `modeling/bootstrap.py` : intervalles par bootstrap clusterisé sur `player_key` (500 réplications par défaut, seed).
- [ ] Interface commune :
  ```python
  class RiskModel(Protocol):
      name: str

      def fit(self, train: pl.DataFrame, valid: pl.DataFrame | None = None) -> "RiskModel": ...
      def predict_proba(self, df: pl.DataFrame) -> np.ndarray: ...  # P(blessure) par ligne jouée
      def params(self) -> dict[str, Any]: ...
  ```
- [ ] `modeling/runner.py` : `run_experiment(model_factory, config) -> ExperimentResult` : boucle sur les folds, métriques par fold et agrégées, figures, log MLflow (params, tags `dataset_version` et `git_sha`, métriques, artefacts).
- [ ] `modeling/report.py` : rapport Markdown par expérience dans `reports/experiments/<run_id>.md` (agrégé, sans `player_key`).
- [ ] CLI `uv run rugby-risk train <model_name> --config configs/experiments/<name>.yaml`.
- [ ] Garde-fou vie privée : les artefacts MLflow ne contiennent aucune colonne `player_key` (test sur un run synthétique).

## Hors périmètre

- Modèles concrets (F19+).

## Fichiers

| Fichier | Action |
|---|---|
| `src/rugby_risk/modeling/{__init__,validation,metrics,bootstrap,runner,report,base}.py` | créer |
| `configs/experiments/_example.yaml` | créer |

## Tests

- `tests/unit/modeling/test_folds.py` — aucune saison de test dans le train ; ordre temporel ; test final protégé.
- `tests/unit/modeling/test_metrics.py` — valeurs connues (Brier d'une prédiction constante = p(1−p) + biais², pente de calibration ≈ 1 pour un modèle parfaitement calibré simulé).
- `tests/unit/modeling/test_no_random_kfold.py` — grep dans `src/rugby_risk/modeling/`.
- `tests/integration/modeling/test_runner_synthetic.py` — un modèle constant sur données synthétiques F17 : run complet, MLflow local temporaire, rapport généré, aucun `player_key` dans les artefacts.

## Critères d'acceptation

- [ ] Run synthétique bout en bout en moins de 60 s.
- [ ] Impossible d'évaluer sur la saison finale sans le drapeau explicite (test).
- [ ] `make check` vert.

## Journal

