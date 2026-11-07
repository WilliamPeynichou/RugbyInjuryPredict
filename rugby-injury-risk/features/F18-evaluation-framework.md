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

- [x] Ajouter `mlflow`, `scikit-learn`, `matplotlib` (matplotlib déjà présent).
- [x] `modeling/validation.py` :
  - `season_folds(seasons, min_train_seasons=5, test_final="2025-2026", covid_disrupted, allow_final_test) -> list[Fold]` : rolling origin (train < valid < test, saisons consécutives), saison COVID jamais seule en test, test final exclu sans `allow_final_test=True` ;
  - garde-fou : `tests/unit/modeling/test_no_random_kfold.py` greppant `KFold`/`train_test_split`/`ShuffleSplit`/`StratifiedKFold` hors des tests eux-mêmes ; seul `runner.py` produit des folds, via `season_folds`.
- [x] `modeling/metrics.py` : log-loss (robuste classe unique), Brier, Brier skill vs référence, pente/intercept de calibration (régression logistique y ~ logit(p̂), C=inf), courbe de calibration en bins quantiles, PR-AUC, ROC AUC, incidence prédite vs observée ; alertes `AUC > 0,75` et pente hors [0,8 ; 1,2].
- [x] `modeling/bootstrap.py` : bootstrap clusterisé sur `player_key` (500 réplications par défaut, seed) ; un joueur tiré emporte toutes ses lignes (pondération exposition).
- [x] Interface commune (`modeling/base.py`) :
  ```python
  class RiskModel(Protocol):
      name: str

      def fit(self, train: pl.DataFrame, valid: pl.DataFrame | None = None) -> "RiskModel": ...
      def predict_proba(self, df: pl.DataFrame) -> np.ndarray: ...  # P(blessure) par ligne jouée
      def params(self) -> dict[str, Any]: ...
  ```
- [x] `modeling/runner.py` : `run_experiment(model_factory, df, config) -> ExperimentResult` : boucle folds (lignes jouées uniquement), métriques par fold + pooled, bootstrap du Brier par fold et pooled, figure de calibration, rapport, log MLflow (params, tags `dataset_version`/`git_sha`/`allow_final_test`, métriques, artefacts png+md). MLflow en import paresseux : un tracking indisponible ne perd pas le rapport.
- [x] `modeling/report.py` : rapport Markdown par expérience dans `reports/experiments/<run_id>.md` (agrégé, sans `player_key`, mention « association, non causale »).
- [x] CLI `uv run rugby-risk train <model_name> --config configs/experiments/<name>.yaml` (registre dans `modeling/null.py` : modèle `constant`).
- [x] Garde-fou vie privée : test téléchargeant chaque artefact MLflow et grepant `player_key` ; le runner ne logge que des agrégats.

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

- [x] Run synthétique bout en bout en moins de 60 s (mesuré : ~25 s avec bootstrap 50 réplications).
- [x] Impossible d'évaluer sur la saison finale sans le drapeau explicite (test).
- [x] `make check` vert (268 passed).

## Journal

## Journal

- **2026-11-07** : cadre livré avec un modèle nul `constant` (taux de base du train) — non contender, il valide le protocole de bout en bout ; M0 arrive en F19. Décisions : (1) `min_train_seasons` compte les saisons d'estimation hors saison de validation ; (2) backend MLflow = sqlite (`sqlite:///data/mlflow.db`) car le file store est déprécié et bloqué par mlflow 3.x ; (3) le bootstrap ne rejoue pas le modèle : il ré-évalue le Brier pooled sur les prédictions out-of-sample, clusters = `player_key` ; (4) les scores du bootstrap prennent leurs tableaux par défaut (`def f(mask, y=y, p=p)`) pour éviter la capture tardive B023 ; (5) `log_loss` sklearn exige les deux classes : `evaluate` passe `labels=[0, 1]` quand `y` est mono-classe. Écart d'échelle : le test du runner utilise 50 réplications de bootstrap (500 en production) pour rester sous 60 s. Incident : un restore du hook pre-commit a écrasé les fichiers modifiés non stagés (cli, pyproject, docs) après le check — tout a été réappliqué et re-vérifié avant commit.
- **Reste ouvert** : M0–M3 passent tous par `run_experiment` (F19+) ; sensibilités du §3.3 de docs/06 (seuil de confiance, cible, IPW, commotions, COVID) via `configs/experiments/*.yaml` au fil des features.
