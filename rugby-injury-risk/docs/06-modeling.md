# 06 — Modélisation

## 1. Formulation

Unité : une ligne de `ml_player_match` = un joueur éligible pour un match de son équipe.

Deux sous-problèmes, traités séparément :

1. **Sélection** — `π(t) = P(played_t = 1 | X(t⁻))`. Le joueur joue-t-il ? (F21)
2. **Blessure** — `h(t) = P(y_injury_t = 1 | played_t = 1, X(t⁻), minutes_t)`, avec l'exposition en offset `log(minutes_t / 80)` pour les modèles de type Poisson / cloglog. (F19–F23)

Lien cloglog recommandé pour le hazard : `cloglog(h) = η + log(minutes/80)` est cohérent avec un processus de Poisson sous-jacent (taux par heure). La logit est acceptée comme approximation (h petit).

Correction de sélection : poids IPW stabilisés `w = P(played) / π̂(t)`, tronqués aux percentiles 1–99, appliqués aux lignes jouées lors de l'estimation du hazard (F21). Analyse de sensibilité systématique avec et sans poids.

**Courbe livrable** : `h(N | poste, profil de référence)` pour N = 0..15, où le profil de référence fixe les autres features à leur médiane par poste (scénario « médian »), et des scénarios nommés (« international en novembre », « retour de blessure », « rotation courte »). Probabilité cumulée sur K matchs : `1 − ∏ (1 − h_k)`.

## 2. Échelle de modèles

| # | Modèle | Rôle | Feature |
|---|---|---|---|
| M0 | Poisson par poste avec offset exposition | Référence à battre ; pont avec les priors | F19 |
| M1 | Hazard logistique / cloglog : splines naturelles (3–4 ddl) sur `consecutive_matches`, `min_28d`, `apps_20min_365d`, `days_since_last_match`, `age` ; interactions `position_group × spline(consecutive_matches)` et `position_group × min_28d` | Premier modèle interprétable | F20 |
| M1w | M1 + poids IPW | Correction du biais de sélection | F21 |
| M2 | Hiérarchique bayésien (PyMC / bambi) : intercept et pente de `consecutive_matches` par poste, partiellement poolés vers `position_group` puis `unit` ; intercept aléatoire joueur (fragilité) et équipe-saison ; priors informés | **Production** | F22 |
| M3 | LightGBM (binaire), contraintes de monotonie optionnelles, calibration isotone sur une saison de validation | Challenger, exploration des interactions | F23 |
| S1 | Gravité : régression log-normale / gamma sur `days_missed` (ou AFT), censure gérée | Burden = incidence × gravité | F24 |

### Priors du modèle M2 (point de départ, à documenter dans le journal de F22)

- Intercept global (échelle cloglog, par match complet) : centré sur `log(-log(1 − 0.07))` ≈ −2,62, écart-type 0,5 (couvre 4–12 %).
- Écart d'intercept par poste : Normal(0, σ_pos), σ_pos ~ HalfNormal(0,3).
- Pente `consecutive_matches` (standardisée) : Normal(0, 0,2) par groupe, partiellement poolée.
- Fragilité joueur : Normal(0, σ_player), σ_player ~ HalfNormal(0,5).
- Équipe-saison : Normal(0, σ_team), σ_team ~ HalfNormal(0,3).
- Effets de charge mensuelle : prior faiblement informatif centré sur log(1,14) par +3,2 FGE sur 30 j (Williams 2017), écart-type large (0,15).

Vérifier par **prior predictive check** que l'incidence simulée par poste reste dans 30–150 / 1000 h.

## 3. Validation

### 3.1 Splits par saison (rolling origin)

```
Fold 1 : train ≤ 2018-2019  | valid 2019-2020* | test 2020-2021**
Fold 2 : train ≤ 2019-2020  | valid 2020-2021  | test 2021-2022
...
Fold k : train ≤ 2023-2024  | valid 2024-2025  | test 2025-2026  ← test final gelé
```
\* 2019-2020 interrompue (COVID) : `is_covid_disrupted = true`, gardée en train avec flag, jamais seule en test.
\** Les saisons de test COVID sont reportées à part.

La saison de validation sert au réglage des hyperparamètres et à la calibration isotone (M3). La saison **2025-2026** est un test final, touché une seule fois par version majeure.

### 3.2 Métriques

| Métrique | Rôle |
|---|---|
| Log-loss | **Sélection de modèle** |
| Brier score, Brier skill score vs M0 | Sélection + communication |
| Pente et intercept de calibration (régression logistique de y sur logit(p̂)) | Critère d'acceptation : pente ∈ [0,8 ; 1,2] par `position_group` |
| Courbes de calibration (10 bins quantiles) par `position_group` | Rapport |
| Incidence prédite vs observée par poste × saison | Rapport, contrôle de dérive |
| PR-AUC | Informatif (prévalence faible) |
| ROC AUC | Informatif uniquement ; > 0,75 → alerte fuite |

Intervalles : bootstrap par **joueur** (clusters) sur la saison de test, 500 réplications.

### 3.3 Analyses de sensibilité obligatoires

1. Seuil de confiance blessure : 0,5 / 0,6 / 0,8.
2. Cible : `y_injury` (match) vs `y_injury_any_7d`.
3. Avec / sans IPW.
4. Avec / sans commotions.
5. Exclusion des saisons COVID.

## 4. Interprétabilité

- M2 : effets marginaux et courbes h(N) par poste avec intervalles crédibles à 90 % (livrable principal).
- M3 : SHAP (TreeExplainer), dépendances ALE par `position_group`.
- Toutes les figures portent la mention « association, non causale ».

## 5. Suivi d'expériences (MLflow)

Chaque run logge :
- `params` : modèle, features, seuil de confiance, variante de cible, folds, seed ;
- `tags` : `dataset_version` (hash dbt de `ml_player_match`), `git_sha`, `feature_set_version` ;
- `metrics` : par fold et agrégées ;
- `artifacts` : courbes de calibration, h(N) par poste, tableau incidence prédite/observée, modèle sérialisé (NetCDF ArviZ pour M2, txt LightGBM pour M3).

Promotion en production : **manuelle**, après revue du rapport de calibration (`reports/model_review_<version>.md`, généré en F22).

## 6. Critères de rejet d'un modèle

- Brier skill score ≤ 0 sur la moyenne des folds.
- Pente de calibration hors [0,8 ; 1,2] sur un groupe de postes.
- AUC > 0,75 non expliquée.
- Divergences MCMC (R̂ > 1,01, ESS < 400, divergences > 0) pour M2.
