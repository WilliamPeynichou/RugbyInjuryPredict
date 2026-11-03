# F22 — Modèle hiérarchique bayésien par poste (production)

| Champ | Valeur |
|---|---|
| Phase | 5 |
| Dépendances | F21 |
| Estimation | L |
| Docs de référence | `docs/06-modeling.md` §2 (M2 et priors), §3, §6, `docs/02-science-priors.md` |

## Objectif

Construire le modèle de production M2 : hazard cloglog hiérarchique avec effets par poste partiellement poolés, fragilité joueur et effet équipe-saison, priors informés, poids IPW, et produire les courbes h(N) avec intervalles crédibles.

## Contexte

Petits effectifs par poste, événements rares, structure emboîtée : le cadre bayésien hiérarchique est le plus adapté et donne directement l'incertitude publiée.

## Périmètre

- [ ] Ajouter `pymc`, `bambi`, `arviz` (et `nutpie` ou `numpyro` comme sampler si gain de temps, justifié dans le journal).
- [ ] `modeling/hierarchical.py` : `HierarchicalHazardModel` implémentant `RiskModel` :
  - intercept global + écarts `unit` → `position_group` → `position_code` (non centrés) ;
  - pente de `consecutive_matches` (standardisée) par `position_group` partiellement poolée ;
  - effets fixes : splines (B-splines, 3–4 nœuds) sur `min_28d`, `apps_20min_365d`, `days_since_last_match_capped`, `age` ; `short_turnaround`, `intl_window`, `recent_return_8w`, `n_prior_injuries_365d`, `prior_concussions_365d`, `surface`, `is_playoff`, `season_period` ;
  - effet aléatoire joueur (`player_key`) et équipe-saison ;
  - offset `log(minutes/80)` ; poids IPW (F21) via vraisemblance pondérée (`pm.Potential`).
- [ ] Priors exactement ceux de `docs/06-modeling.md` §2, centralisés dans `modeling/priors.py`.
- [ ] **Prior predictive check** : incidence simulée par poste dans 30–150 / 1000 h (test automatique sur le modèle compilé).
- [ ] Diagnostics : R̂ ≤ 1,01, ESS bulk et tail ≥ 400, 0 divergence ; sinon le run est marqué `failed`.
- [ ] Prédiction hors échantillon : joueurs nouveaux → effet joueur intégré (tirage dans la loi de population), pas mis à 0.
- [ ] Courbes h(N) par `position_code` et scénario avec intervalles crédibles à 90 % (moyenne postérieure sur tirages) → `curves.py`.
- [ ] Sauvegarde : `InferenceData` NetCDF en artefact MLflow ; enregistrement dans le registre MLflow (`rugby-risk-m2`) **sans** promotion automatique.
- [ ] Rapport de revue `reports/model_review_<version>.md` : métriques par fold vs M0/M1/M1w, calibration par groupe, courbes par poste, diagnostics, sensibilités obligatoires (`docs/06-modeling.md` §3.3), critères de rejet (§6) cochés.
- [ ] Option `--fast` (sous-échantillonnage stratifié, 2 chaînes, 500 tirages) pour itérer.

## Hors périmètre

- Promotion en production (humaine). Export (F25).

## Spécification technique

Temps de calcul à surveiller : si un fold dépasse 30 min, consigner dans le journal et envisager l'approximation ADVI pour l'exploration (jamais pour la version publiée) ou le sous-échantillonnage des non-événements avec correction d'offset (cas-témoin) documentée.

## Fichiers

| Fichier | Action |
|---|---|
| `src/rugby_risk/modeling/hierarchical.py` | créer |
| `src/rugby_risk/modeling/{priors,curves}.py` | modifier |
| `src/rugby_risk/modeling/review.py` (rapport de revue) | créer |
| `configs/experiments/m2_hierarchical.yaml` | créer |

## Tests

- `tests/unit/modeling/test_prior_predictive.py` — incidence simulée dans la plage.
- `tests/slow/modeling/test_hierarchical_recovery.py` (marqueur `slow`) — données synthétiques avec effets par poste connus : intervalles à 90 % couvrent les vraies valeurs pour ≥ 8 postes sur 9.
- `tests/unit/modeling/test_new_player_prediction.py` — un joueur inconnu reçoit une prédiction finie intégrant la variance de population.
- `tests/integration/modeling/test_m2_fast_run.py` — run `--fast` complet et rapport de revue généré.

## Critères d'acceptation

- [ ] Diagnostics MCMC conformes sur le run de référence.
- [ ] Rapport de revue généré avec tous les critères de `docs/06-modeling.md` §6.
- [ ] Sur données réelles : pente de calibration par groupe consignée dans le journal ; décision de promotion prise par l'humain.
- [ ] `make check` vert (tests `slow` exécutés séparément via `make test-slow`).

## Journal

