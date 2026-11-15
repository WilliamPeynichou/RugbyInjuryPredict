# F20 — Hazard en temps discret

| Champ | Valeur |
|---|---|
| Phase | 4 |
| Dépendances | F19 |
| Estimation | M |
| Docs de référence | `docs/06-modeling.md` §1–2 (M1), §3, `docs/05-features-spec.md` |

## Objectif

Premier modèle interprétable de charge : régression binomiale (lien cloglog avec offset d'exposition, logit en alternative) avec splines et interactions poste × charge, et production des premières courbes h(N) par poste.

## Contexte

M1 répond déjà à la question du projet, sans correction de sélection. Il sert de base à M1w (F21), de structure pour M2 (F22) et de point de comparaison pour M3 (F23).

## Périmètre

- [x] Ajouter `statsmodels`, `patsy` (ou `formulaic`).
- [x] `modeling/hazard.py` : `DiscreteHazardModel(formula, link="cloglog", offset="log_exposure")` implémentant `RiskModel` (F18).
- [x] Formule par défaut :
  ```
  y_injury ~ C(position_group)
           + cr(consecutive_matches, df=4) + C(position_group):consecutive_matches
           + cr(min_28d, df=3) + C(position_group):min_28d
           + cr(apps_20min_365d, df=3)
           + cr(days_since_last_match_capped, df=3) + short_turnaround
           + intl_window + recent_return_8w + n_prior_injuries_365d + prior_concussions_365d
           + cr(age, df=3) + C(surface) + is_playoff + C(season_period)
  ```
  avec `log_exposure = log(minutes_played / 80)`, `days_since_last_match_capped = min(x, 60)`.
- [x] Standardisation des variables continues (paramètres appris sur le train uniquement).
- [x] `modeling/curves.py` : `hazard_curve(model, position_code, n_range=range(0,16), scenario="median")` ; profils de scénario définis dans `configs/scenarios.yaml` (`median`, `international_november`, `return_from_injury`, `short_turnaround_block`) avec valeurs **par poste** calculées sur le train (médianes).
- [x] Probabilité cumulée sur K matchs (`cumulative_risk`).
- [x] Intervalles des courbes : bootstrap par joueur (F18) — 200 réplications par défaut pour M1.
- [x] Configs `m1_hazard_cloglog.yaml`, `m1_hazard_logit.yaml` ; comparaison des deux liens dans le rapport.

## Hors périmètre

- IPW (F21), effets aléatoires (F22).

## Spécification technique

Matrice de design construite par une fonction pure `build_design(df, spec, fitted_transform=None)` pour garantir que les transformations du train sont réappliquées telles quelles au test (pas de fuite par standardisation).

## Fichiers

| Fichier | Action |
|---|---|
| `src/rugby_risk/modeling/{hazard,curves,design}.py` | créer |
| `configs/scenarios.yaml`, `configs/experiments/m1_*.yaml` | créer |

## Tests

- `tests/unit/modeling/test_design.py` — standardisation apprise sur train réappliquée au test ; colonnes interdites (`TARGET_AND_EXPOSURE_COLUMNS` hors offset) rejetées.
- `tests/unit/modeling/test_hazard_recovery.py` — sur données synthétiques avec effet connu de `consecutive_matches` (log-HR = 0,05 par match pour les avants, 0 pour les arrières), les coefficients estimés retrouvent l'effet (IC 95 %).
- `tests/unit/modeling/test_curves.py` — courbe monotone quand l'effet simulé l'est ; probabilité cumulée correcte.
- `tests/integration/modeling/test_m1_run.py` — run complet, Brier skill score > 0 vs M0 sur données synthétiques avec effets de charge.

## Critères d'acceptation

- [x] Récupération des effets simulés (test).
- [x] Courbes h(N) par poste générées (figure + table) dans le rapport MLflow.
- [x] Sur données réelles (quand disponibles) : Brier skill score vs M0 consigné dans le journal, par fold.
- [x] `make check` vert.

## Journal

### 2026-11-08 — implémentation (branche `feat/F20-discrete-hazard`)

**Livré**
- Dépendances `statsmodels`, `patsy` (pandas transitif ; overrides mypy `statsmodels.*`,
  `patsy.*`, `pandas.*`).
- `modeling/design.py` : `DesignSpec` (termes de la formule par défaut) et
  `build_design(df, spec, fitted=None)` pure. Tout est appris sur le train et réappliqué :
  médianes d'imputation, bornes de winsorisation (quantiles 1/99 % du train), moyenne/écart-type
  (continues seulement, binaires laissées en 0/1), modalités, nœuds des splines (`DesignInfo`
  patsy). Modalité inconnue au test → modalité de référence du train. `validate_spec` refuse
  cibles, exposition du match t (hors offset), identifiants et colonnes interdites.
- `modeling/hazard.py` : `DiscreteHazardModel(link="cloglog"|"logit", spec, curve_replications)`
  (GLM binomial statsmodels, offset `log(minutes/80)`), `coefficients()` (IC Wald 95 %), tables
  et figure de rapport. Registre : `m1_hazard_cloglog`, `m1_hazard_logit`.
- `modeling/curves.py` : `load_scenarios`, `scenario_profiles` (médianes par poste sur le train),
  `hazard_curve`, `cumulative_risk`. `configs/scenarios.yaml` (4 scénarios, N = 0..15).
- Bandes des courbes : bootstrap par joueur (refit complet, transformations réapprises dans
  chaque réplication), 200 réplications par défaut, IC90.
- Runner F18 : hook `report_figures` (courbes h(N) loguées dans MLflow), Brier skill vs M0
  global **par fold** (table des folds), comptage des labels censurés exclus.

**Écarts à la fiche (décidés, testés)**
- Interactions poste × charge construites à la main (pente par groupe hors référence) au lieu de
  `C(g):x` : patsy code `C(g):x` en plein rang, colinéaire avec la partie linéaire de
  `cr(x)` → matrice singulière. Rang plein vérifié (33/33 colonnes).
- `cr(..., constraints='center')` : sans contrainte la base somme à 1 (colinéaire à
  l'intercept).
- Termes dégénérés au train écartés et listés (`FittedTransform.dropped`, param MLflow
  `dropped_terms`) : variable toute nulle ou constante, binaire dont la modalité minoritaire a
  < 30 lignes (quasi-séparation). Sur les vraies données : `age` (100 % NULL, birth_date
  manquant F09), `surface`, `season_period`, `short_turnaround`, `prior_concussions_365d`
  (constants), `is_playoff` (23 lignes après exclusion de la censure).
- Le scénario `short_turnaround_block` n'agit que via `days_since_last_match = 6` tant que
  `short_turnaround` est constant dans les données.
- Comparaison des liens : AIC in-sample dans chaque rapport + comparaison hors échantillon des
  deux runs ci-dessous.

**Bug de données trouvé : censure du label en fin de saison**
- `y_injury` vient des absences (F13) : `injury_candidate` exige ≥ 2 matchs d'équipe manqués.
  Sans ces matchs (fin de saison, élimination, départ), `y = 0` veut dire « non observable ».
  Constat réel : 0 blessure sur 677 lignes de phase finale (≈ 11 attendues) ; taux par nombre
  de matchs de suivi restants 0 / 0,5 / 1,1 / 1,7 % pour 0 / 1 / 2 / ≥ 3.
- Correction (doc de recherche §1.4 « Censure ») : `validation.with_label_observability`
  marque les lignes avec ≥ `absence_signal.min_matches_injury_candidate` matchs suivants du
  joueur dans la saison (seuil lu dans `config/injury_rules.yaml`, pas réglé sur l'outcome ; le
  calcul ne lit jamais la cible, testé). Le runner exclut les autres du fit **et** de
  l'évaluation, pour tous les modèles : 1 977 lignes jouées exclues sur le réel.
- Effet : M0 refait sur la même base (chiffres ci-dessous) ; les chiffres F19 du Journal F19
  incluaient ces faux négatifs.

**Résultats réels** (`dataset_version e8591d016b97059bae784a823a81b005`, train 2022-23,
valid 2023-24 non utilisée, test 2024-25, 7 819 lignes, prévalence 1,71 %)

| Modèle | Log-loss | Brier | Brier skill vs M0 global (fold 0) | ROC AUC | Pente calib. | Incidence prédite |
|---|---|---|---|---|---|---|
| M0 par poste | 0,0979 | 0,01716 | +0,0001 | 0,35 | −0,69 | 1,78 % |
| M1 cloglog | 0,0983 | 0,01704 | +0,0071 | 0,49 | −0,01 | 1,36 % |
| M1 logit | 0,0982 | 0,01705 | +0,0066 | 0,49 | −0,00 | 1,38 % |

- AIC train : cloglog 1 595,8, logit 1 593,6 (écart négligeable).
- Lecture : M1 ne généralise pas encore. Brier légèrement meilleur, log-loss légèrement moins
  bon que M0, AUC ≈ 0,5, pente de calibration ≈ 0 et incidence sous-estimée (1,36 % vs
  1,71 %). Cause principale : une seule saison d'estimation (~115 événements pour 32
  paramètres, ≈ 4 événements par paramètre). Pas de réglage sur le test (interdit) : la
  réponse est plus de saisons (crawl 2018-2022) et la régularisation hiérarchique (F22).
- Courbes h(N) décroissantes avec N pour la plupart des postes (ex. BACK_ROW 0,024 → 0,003),
  croissantes pour les demis (SCRUM_HALF/FLY_HALF). La décroissance est le biais du
  « survivant en bonne santé » attendu sans correction de sélection : objet de F21 (IPW).
- Coefficients notables (log-HR) : `n_prior_injuries_365d` +0,49 par écart-type
  (IC95 [0,36 ; 0,63]) ; `recent_return_8w` −1,61 (IC95 [−2,68 ; −0,54]), suspect : une
  rechute < 7 j après retour est fusionnée avec l'épisode précédent (`merge_gap_days`),
  sous-détection probable à vérifier en F21/F16.

**Non vérifié / risques**
- Seuil de suivi = 2 matchs : le taux à 2 matchs restants (1,1 %) reste sous le taux à ≥ 3
  (1,7 %) ; censure résiduelle possible, non corrigée pour ne pas régler le seuil sur l'outcome.
- Bootstrap des courbes ≈ 3 min par run (200 refits) ; à surveiller quand le train passera à
  5 saisons.
