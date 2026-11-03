# F19 — Baseline Poisson par poste et priors

| Champ | Valeur |
|---|---|
| Phase | 4 |
| Dépendances | F18 |
| Estimation | S |
| Docs de référence | `docs/06-modeling.md` §2 (M0), `docs/02-science-priors.md` §1–2 |

## Objectif

Établir la référence à battre (M0) : un taux de blessure par poste et par heure d'exposition, et centraliser les priors épidémiologiques.

## Contexte

Le Brier skill score de tous les modèles est calculé contre M0. M0 sert aussi de pont avec la littérature : son taux par 1000 h doit être comparable aux priors (avec la sous-déclaration attendue).

## Périmètre

- [ ] `modeling/priors.py` : constantes de `docs/02-science-priors.md` §1 (incidences, gravités, IC), fonction `rate_to_match_prob(rate_per_1000h, minutes)`, et `PRIORS_VERSION`.
- [ ] `modeling/baselines.py` :
  - `PositionRateModel` : taux λ_p = blessures / heures d'exposition par `position_code`, estimé sur le train ; prédiction `1 − exp(−λ_p · minutes/60)` ;
  - option de lissage empirique-bayésien vers le taux du `position_group` (gamma-Poisson) pour les postes à faible effectif ;
  - `GlobalRateModel` (un seul λ) pour comparaison.
- [ ] Config d'expérience `configs/experiments/m0_position_rate.yaml`.
- [ ] Rapport : taux par poste (par 1000 h) avec IC, comparé aux priors (Premiership, talonneur, commotion).

## Hors périmètre

- Covariables de charge (F20).

## Spécification technique

Les prédictions ne portent que sur les lignes `played = true` ; les lignes non jouées sont ignorées par M0 (elles serviront en F21).

## Fichiers

| Fichier | Action |
|---|---|
| `src/rugby_risk/modeling/{priors,baselines}.py` | créer |
| `configs/experiments/m0_position_rate.yaml` | créer |

## Tests

- `tests/unit/modeling/test_priors.py` — `rate_to_match_prob(76, 80) ≈ 0.096` (± 0,002) ; `rate_to_match_prob(114, 80) ≈ 0.14`.
- `tests/unit/modeling/test_baselines.py` — sur données synthétiques avec taux par poste injectés, les taux estimés sont dans l'IC à 95 % ; lissage vers le groupe quand l'exposition est faible.
- `tests/integration/modeling/test_m0_run.py` — run complet via le runner F18.

## Critères d'acceptation

- [ ] Aucune constante épidémiologique ailleurs que dans `priors.py` (test grep sur `76`, `114`, `18.4` dans `src/rugby_risk/modeling/` hors `priors.py`).
- [ ] Run MLflow M0 enregistré avec rapport.
- [ ] `make check` vert.

## Journal

