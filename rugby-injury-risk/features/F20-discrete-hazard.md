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

- [ ] Ajouter `statsmodels`, `patsy` (ou `formulaic`).
- [ ] `modeling/hazard.py` : `DiscreteHazardModel(formula, link="cloglog", offset="log_exposure")` implémentant `RiskModel` (F18).
- [ ] Formule par défaut :
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
- [ ] Standardisation des variables continues (paramètres appris sur le train uniquement).
- [ ] `modeling/curves.py` : `hazard_curve(model, position_code, n_range=range(0,16), scenario="median")` ; profils de scénario définis dans `configs/scenarios.yaml` (`median`, `international_november`, `return_from_injury`, `short_turnaround_block`) avec valeurs **par poste** calculées sur le train (médianes).
- [ ] Probabilité cumulée sur K matchs (`cumulative_risk`).
- [ ] Intervalles des courbes : bootstrap par joueur (F18) — 200 réplications par défaut pour M1.
- [ ] Configs `m1_hazard_cloglog.yaml`, `m1_hazard_logit.yaml` ; comparaison des deux liens dans le rapport.

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

- [ ] Récupération des effets simulés (test).
- [ ] Courbes h(N) par poste générées (figure + table) dans le rapport MLflow.
- [ ] Sur données réelles (quand disponibles) : Brier skill score vs M0 consigné dans le journal, par fold.
- [ ] `make check` vert.

## Journal

