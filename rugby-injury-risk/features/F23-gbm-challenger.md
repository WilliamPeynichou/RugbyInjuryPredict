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

- [x] Ajouter `lightgbm`, `shap`.
- [x] `modeling/gbm.py` : `GBMRiskModel` (objectif `binary`, exposition intégrée en feature `log_exposure` **et** via `init_score` en option, choix documenté) ; `position_code` en catégorielle native.
- [x] Contraintes de monotonie optionnelles (config) sur `days_since_last_match` (non croissante après 60 j…) — désactivées par défaut.
- [x] Réglage des hyperparamètres sur la saison de validation de chaque fold (Optuna léger ou grille réduite, 30 essais max), métrique log-loss.
- [x] Calibration isotone sur la saison de validation, appliquée au test.
- [x] Interprétabilité : SHAP TreeExplainer (valeurs globales, dépendance de `consecutive_matches` par `position_group`), ALE par groupe (implémentation simple dans `modeling/ale.py`).
- [x] Courbes h(N) par poste via `curves.py` (profil de scénario) pour comparaison avec M2.
- [x] Rapport : M3 vs M2 vs M1w (log-loss, Brier, calibration), avis sur les interactions manquées par M1/M2.

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

- [x] Run M3 complet avec rapport comparatif.
- [x] Alerte automatique si AUC > 0,75 (héritée de F18) traitée dans le journal.
- [x] `make check` vert.

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
- **Run réel n°1 (2026-11-09, `m3_gbm-20261109T182710Z`) — alerte AUC traitée** : ROC AUC
  0,90 (alerte F18 > 0,75), `log_exposure` premier en SHAP, courbes h(N) à 80 min toutes à 0.
  Diagnostic : causalité inverse. Un joueur blessé est remplacé tôt et le label s'appuie en
  partie sur la sortie précoce (F12) : l'exposition libre apprend « peu de minutes =
  blessure ». Le doc de recherche impose l'exposition en **offset** (docs/06 §2) et autorise
  des contraintes de monotonie pour le GBM. Correctif : `log_exposure` sous contrainte
  **monotone croissante imposée** (non désactivable, appliquée aussi pendant la grille ;
  avant, la grille tournait sans contrainte → réglage incohérent). Tests :
  `test_exposure_never_decreases_risk`, `test_exposure_constraint_cannot_be_disabled`.
- **Run réel n°2 (référence F23) `m3_gbm-20261109T182944Z`**, dataset_version
  `7d004d9a146715b139e501738e58620a`, git `ac3bd9b` + correctif, fold unique test 2024-2025
  (7 819 lignes jouées, prévalence 1,71 %) :

  | Modèle | Log-loss | Brier | Brier skill | ROC AUC | Pente calib. |
  |---|---|---|---|---|---|
  | M0 poste (Poisson offset) | 0,0979 | 0,01716 | 0,0001 | 0,35 | −0,69 |
  | M1 hazard cloglog | 0,0983 | 0,01704 | 0,0071 | 0,49 | −0,01 |
  | M1w (IPW) | 0,1043 | 0,01726 | −0,0055 | 0,50 | 0,08 |
  | M2 hiérarchique (revue F22) | 0,0997 | 0,01769 | −0,0307 | 0,48 | −0,04 |
  | **M3 GBM (offset monotone)** | **0,0845** | **0,01655** | **0,0358** | 0,63 | 0,77 |

  Brier IC90 bootstrap joueur M3 : [0,01498 ; 0,01857]. Alerte restante : pente 0,77 hors
  [0,8 ; 1,2] ; pente par groupe hors bornes pour back_row (0,18), centre (0,67), lock (−0,01)
  (14 à 28 blessures par groupe : très bruité).
- **Lecture** : M3 est le seul modèle qui bat la référence en log-loss et Brier. Le gain vient
  des features **hors** M1/M2 (SHAP : `days_since_last_injury`, `days_since_last_match`,
  `season_minutes`, `recent_return_8w`, puis `height_missing`/`weight_missing`), pas d'une
  interaction poste x enchaînement : ALE de `consecutive_matches` par groupe dans ±0,003
  sans tendance, courbes h(N) M3 plates ou légèrement décroissantes (0,8 % talonneur à
  4,4 % arrière). Interactions manquées par M1/M2 : **historique de blessure** (réblessure)
  et **indicateurs de profil manquant** — ces derniers sont un artefact de couverture
  (joueurs peu documentés = effectifs de rotation), à ne pas interpréter. Conclusion
  identique à M2 : aucune hausse établie du risque avec l'enchaînement sur 3 saisons.
- **Décision** : M3 non promu (1 fold, pente hors bornes, pas de correction de sélection).
  Piste pour M2 (décision humaine) : ajouter `days_since_last_injury` au design hiérarchique.
  Aucune exposition publique de M3 (hors périmètre).


- **Run M3 sans indicateurs `*_missing` (2026-11-11, `m3_gbm-20261111T161235Z`)** : métriques
  **identiques** à la référence (log-loss 0,0845, Brier 0,01655, skill +0,0358, AUC 0,6314,
  pente 0,773). Retirer les `*_missing` ne change rien : le gain de M3 ne vient pas d'eux.
  SHAP : `days_since_last_injury` (2,33), `days_since_last_match` (1,23), `recent_return_8w`,
  `season_minutes`, puis `weight_kg` (0,69, nouveau en tête : possible proxy de poste ou de
  rotation, à surveiller), `bmi_rel_position`. Conclusion inchangée : gain réel mais pente
  hors bornes, M3 non promu.
- **Variante M2 `m2_hierarchical_injhist`** : code, config et tests (sans fit). Run réel non
  lancé : `uv run rugby-risk train m2_hierarchical_injhist --config
  configs/experiments/m2_hierarchical_injhist.yaml` (~20 min). Critère fixé à l'avance :
  intéressante seulement si log-loss < 0,0979 (M0) ET pente dans [0,8 ; 1,2].
