# F21 — Modèle de sélection et pondération IPW

| Champ | Valeur |
|---|---|
| Phase | 5 |
| Dépendances | F20 |
| Estimation | M |
| Docs de référence | `docs/06-modeling.md` §1, §3.3, `docs/02-science-priors.md` §3, §6 |

## Objectif

Modéliser la probabilité qu'un joueur éligible joue (`π(t)`) et corriger le biais de sélection (« survivant en bonne santé ») du hazard par pondération inverse (M1w).

## Contexte

Les joueurs qui enchaînent sont les plus robustes, et les staffs mettent au repos les joueurs fatigués avant qu'ils ne se blessent. Sans correction, l'effet des longues séquences est sous-estimé, voire inversé.

## Périmètre

- [ ] `modeling/selection.py` : `SelectionModel` (régression logistique régularisée, ou LightGBM calibré si mieux en log-loss) prédisant `played` sur **toutes** les lignes éligibles, avec les features as-of (pas d'information du match `t`).
- [ ] Exclusion des absences de motif connu non-blessure (`international_duty` vu du club, `suspension`) de l'ensemble de risque ou en covariable — choix argumenté dans le journal.
- [ ] Poids stabilisés `w = P̂(played) / π̂(t)` avec `P̂(played)` estimé par poste ; troncature aux percentiles 1 et 99 ; diagnostics (distribution des poids, ESS effectif).
- [ ] Les poids sont calculés **dans chaque fold** avec le modèle de sélection entraîné sur le train du fold uniquement.
- [ ] `DiscreteHazardModel` (F20) accepte `weights` ; config `m1w_hazard_ipw.yaml`.
- [ ] Rapport comparatif M1 vs M1w : coefficients de charge, courbes h(N) superposées par poste, métriques.
- [ ] Analyse de sensibilité : troncature 5–95, sans stabilisation.

## Hors périmètre

- Méthodes causales avancées (g-formula, modèles structuraux marginaux complets) : noter comme piste dans le journal.

## Spécification technique

Calibration du modèle de sélection vérifiée (pente ∈ [0,8 ; 1,2]) avant usage des poids : sinon l'IPW est désactivé pour le fold et un avertissement est loggé.

## Fichiers

| Fichier | Action |
|---|---|
| `src/rugby_risk/modeling/selection.py` | créer |
| `src/rugby_risk/modeling/hazard.py` | modifier (poids) |
| `configs/experiments/m1w_hazard_ipw.yaml` | créer |

## Tests

- `tests/unit/modeling/test_selection_bias.py` — simulation : fragilité latente qui réduit `π` et augmente `h` ; le M1 naïf sous-estime l'effet des séquences, M1w s'en rapproche (erreur relative réduite d'au moins 50 %).
- `tests/unit/modeling/test_weights.py` — stabilisation, troncature, ESS.
- `tests/integration/modeling/test_m1w_run.py` — run complet.

## Critères d'acceptation

- [ ] Test de simulation du biais vert.
- [ ] Rapport M1 vs M1w généré.
- [ ] `make check` vert.

## Journal

