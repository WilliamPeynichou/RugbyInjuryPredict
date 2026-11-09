# F23 — Challenger gradient boosting et SHAP

| Champ | Valeur |
|---|---|
| Phase | 6 |
| Dépendances | F20 |
| Estimation | M |
| Docs de référence | `docs/06-modeling.md` §2 (M3), §4 |

## Objectif

Tester si un modèle non paramétrique (LightGBM calibré) apporte un gain de log-loss en validation temporelle et explorer les interactions poste × charge avec SHAP et ALE.

## Contexte

M3 n'est pas destiné à la production publique sauf gain clair et calibration correcte : c'est un outil de vérification (le modèle paramétrique rate-t-il une interaction ?) et d'exploration.

## Périmètre

- [ ] Ajouter `lightgbm`, `shap`.
- [ ] `modeling/gbm.py` : `GBMRiskModel` (objectif `binary`, exposition intégrée en feature `log_exposure` **et** via `init_score` en option, choix documenté) ; `position_code` en catégorielle native.
- [ ] Contraintes de monotonie optionnelles (config) sur `days_since_last_match` (non croissante après 60 j…) — désactivées par défaut.
- [ ] Réglage des hyperparamètres sur la saison de validation de chaque fold (Optuna léger ou grille réduite, 30 essais max), métrique log-loss.
- [ ] Calibration isotone sur la saison de validation, appliquée au test.
- [ ] Interprétabilité : SHAP TreeExplainer (valeurs globales, dépendance de `consecutive_matches` par `position_group`), ALE par groupe (implémentation simple dans `modeling/ale.py`).
- [ ] Courbes h(N) par poste via `curves.py` (profil de scénario) pour comparaison avec M2.
- [ ] Rapport : M3 vs M2 vs M1w (log-loss, Brier, calibration), avis sur les interactions manquées par M1/M2.

## Hors périmètre

- Exposition publique de M3 (uniquement si décision humaine documentée).

## Fichiers

| Fichier | Action |
|---|---|
| `src/rugby_risk/modeling/{gbm,ale}.py` | créer |
| `configs/experiments/m3_gbm.yaml` | créer |

## Tests

- `tests/unit/modeling/test_gbm.py` — calibration isotone apprise sur valid uniquement ; pas de fuite des hyperparamètres vers le test.
- `tests/unit/modeling/test_ale.py` — ALE d'une fonction connue.
- `tests/integration/modeling/test_m3_run.py` — run complet sur synthétique, interaction poste × charge simulée retrouvée dans SHAP.

## Critères d'acceptation

- [ ] Run M3 complet avec rapport comparatif.
- [ ] Alerte automatique si AUC > 0,75 (héritée de F18) traitée dans le journal.
- [ ] `make check` vert.

## Journal

- **Implémentation** : LightGBM envisagé mais écarté : la bibliothèque native exige
  `libomp`, une dépendance système absente de la machine de développement (x86_64). Choix
  documenté : `sklearn.ensemble.HistGradientBoostingClassifier` — même famille d'algorithme
  (gradient boosting par histogrammes), déjà en dépendance du projet, `uv sync` suffit.
  `shap` ajouté (TreeExplainer supporte ce modèle).
- **Exposition** : `log_exposure = log(minutes_played/80)` en feature unique — un canal unique
  garde SHAP et la calibration isotone cohérents ; `init_score` contournerait la calibration.
- **Features** : colonnes du registre FEATURES, numériques/booléennes uniquement
  (arbres : NaN natifs, sentineles 999 conservées) ; `position_code` en catégorielle native
  sklearn ; `position_group`/`unit`/`surface`/`competition_code` écartés (redondants ou
  textuels) ; colonnes 100 % nulles au train écartées (terme dégénéré).
- **Protocole** : grille réduite de 8 combinaisons (learning_rate, max_leaf_nodes,
  min_samples_leaf), réglée sur la saison de validation par log-loss ; calibration isotone
  apprise sur la validation du modèle final, appliquée au test. SHAP (moyenne |valeur|) et
  ALE de `consecutive_matches` par groupe calculés sur la validation, dans le rapport
  d'expérience via `report_tables`. SHAP reçoit une matrice numérique (catégorielles en
  codes) car l'backend arrow de pandas refuse les strings.
- **Tests** : unitaires (calibration sur validation uniquement, courbes, garde-fous) et
  intégration (run complet via le runner F18 + SHAP retrouve l'interaction unit x
  consecutive simulée — DGP hazard_frame avec pente avants 0,15 / arrières 0). 3 saisons
  synthétiques -> 1 fold, comme le réel.
- **Reste à faire** : run M3 réel (`rugby-risk train m3_gbm --config
  configs/experiments/m3_gbm.yaml`), tableau comparatif M3 vs M2 vs M1w dans ce journal,
  puis F27 (front).

