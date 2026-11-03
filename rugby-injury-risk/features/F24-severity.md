# F24 — Modèle de gravité

| Champ | Valeur |
|---|---|
| Phase | 6 |
| Dépendances | F18 |
| Estimation | M |
| Docs de référence | `docs/06-modeling.md` §2 (S1), `docs/02-science-priors.md` §1, §3 |

## Objectif

Modéliser la durée d'indisponibilité (`days_missed`) conditionnellement à une blessure, pour estimer le burden (incidence × gravité) par poste et selon la charge.

## Contexte

Williams et al. 2023 montrent que la charge élevée d'une saison est associée au burden plutôt qu'à l'incidence : incidence et gravité doivent être modélisées séparément.

## Périmètre

- [ ] Ajouter `lifelines`.
- [ ] `modeling/severity.py` :
  - `SeverityAFTModel` (Weibull ou log-normal AFT, `lifelines`), durée = `days_missed`, événement = `not censored` ;
  - covariables : `position_group`, `is_concussion`, `body_region` regroupée, `consecutive_matches`, `min_28d`, `age`, `n_prior_injuries_365d`, `surface`, `season_period` ;
  - prédiction : médiane et quantiles 25/75 de jours d'absence par poste et scénario.
- [ ] Évaluation par saison (folds F18 adaptés aux épisodes) : C-index, erreur absolue médiane sur les épisodes non censurés, calibration par quantiles.
- [ ] `burden_curve(position_code, n_range)` = h(N) (modèle de production) × gravité attendue → jours d'absence attendus pour 1000 h.
- [ ] Rapport : gravité médiane par poste vs priors (PRISP : médiane 17 j en 2022-23), effet de la surface (gravité +6 j attendue sur synthétique selon le PRISP sur dix saisons).

## Hors périmètre

- Prédiction de la date de retour d'un joueur particulier.

## Spécification technique

Les épisodes à `source_confidence < threshold` sont exclus ; les épisodes « fin de saison » sont censurés à la fin de saison si aucun retour n'est observé.

## Fichiers

| Fichier | Action |
|---|---|
| `src/rugby_risk/modeling/severity.py` | créer |
| `configs/experiments/s1_severity.yaml` | créer |

## Tests

- `tests/unit/modeling/test_severity_recovery.py` — durées log-normales simulées avec effet connu de la commotion (−) et de l'âge (+) : effets retrouvés ; censure correctement prise en compte (biais réduit vs régression naïve).
- `tests/integration/modeling/test_s1_run.py` — run complet et rapport.

## Critères d'acceptation

- [ ] Effets simulés retrouvés (test).
- [ ] Courbes de burden par poste générées.
- [ ] `make check` vert.

## Journal

