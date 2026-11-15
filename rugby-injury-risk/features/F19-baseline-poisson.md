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

- [x] `modeling/priors.py` : constantes de `docs/02-science-priors.md` §1 (incidences, gravités, IC), fonction `rate_to_match_prob(rate_per_1000h, minutes)`, et `PRIORS_VERSION`.
- [x] `modeling/baselines.py` :
  - `PositionRateModel` : taux λ_p = blessures / heures d'exposition par `position_code`, estimé sur le train ; prédiction `1 − exp(−λ_p · minutes/60)` ;
  - option de lissage empirique-bayésien vers le taux du `position_group` (gamma-Poisson) pour les postes à faible effectif ;
  - `GlobalRateModel` (un seul λ) pour comparaison.
- [x] Config d'expérience `configs/experiments/m0_position_rate.yaml`.
- [x] Rapport : taux par poste (par 1000 h) avec IC, comparé aux priors (Premiership, talonneur, commotion).

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

- [x] Aucune constante épidémiologique ailleurs que dans `priors.py` (test grep sur `76`, `114`, `18.4` dans `src/rugby_risk/modeling/` hors `priors.py`).
- [x] Run MLflow M0 enregistré avec rapport.
- [x] `make check` vert.

## Journal

### 2026-11-08 — F19 livrée

**Code.** `modeling/priors.py` (constantes docs/02 §1 centralisées, `rate_to_match_prob`, `PRIORS_VERSION=1.0.0`) ; `modeling/baselines.py` (`GlobalRateModel`, `PositionRateModel` avec lissage gamma-Poisson `smoothing_hours=200` vers le taux du `position_group`, IC Poisson exact de Jeffreys dans le rapport) ; enregistrement dans `null.py:registry()` ; config `configs/experiments/m0_position_rate.yaml`. Runner F18 étendu : Brier skill score calculé contre M0 global (`GlobalRateModel`) à chaque run (docs/06 §3.2) et hook optionnel `report_tables()` rendu dans le rapport. Dépendance `scipy` déclarée (IC gamma). Tests : 15 unitaires (priors + baselines, dont NaN-minutes) + 2 intégration (run complet M0 via runner, skill ≥ −0.02, AUC < 0.75, pas de `player_key` dans le rapport).

**Bugs réels attrapés.**
1. `dim_player.primary_position` NULL à 100 % : `_dim_player.first_position` cherchait des codes (`PROP`…) dans `positions_raw`, mais allrugby fournit des labels FR (`pilier`, `3ème ligne`) et `position_aliases.csv` n'était chargé par personne (seule la source `lnr` y figurait). Fix : loader validé `reference.position_canonical(raw, source)` (CSV étendu aux 9 labels allrugby, schéma pandera, contrôles doublons/codes), lookup par token dans `orchestration/assets/entities.py`. Rebuild entities→marts→ml : 0 UNKNOWN, 9 codes positionnés.
2. 206 lignes `played=true` avec `minutes_played` NULL (trou de parsing, toutes `y_injury=0`) → NaN dans les prédictions. Décision : le runner exclut les lignes jouées sans exposition connue (`_played` filtre `minutes_played`), garde fail-fast `ValueError` dans fit/predict des baselines. Test dédié.
3. Garde exposition nulle contournée (`_Rates.global_rate` par défaut 1e-6 passait le seuil 1e-8) → défaut 0.0.

**Résultat réel** (`rugby-risk train m0_position`, dataset_version `e8591d01`, 3 saisons pilotes) : prévalence 1,61 %, log-loss pooled 0,0928, Brier 0,0161, Brier skill vs M0 global ≈ +0,0001, AUC 0,35. Taux par poste 8,7 (HOOKER) à 30,8 (SCRUM_HALF) /1000 h — sous la bande priors 50–80 attendue : sous-déclaration des signaux F12/F13 (seuils de confiance), cohérent avec l'avertissement docs/02 §2. Pente de calibration hors [0,8;1,2] : attendu pour M0 (spread des prédictions quasi nul), pas une fuite — critère de calibration applicable à M1+.

**Non vérifié / risques.**
- Le rapport M0 de 00:36 (dataset_version `a0f4da1`, 1280 lignes) correspond à un état non reproductible du lac (environnement d'exécution éphémère des shells) ; ignoré, l'état actuel du warehouse est la référence (`e8591d01`).
- Le loader LNR `load_position_aliases` ignore la colonne `source` (superset de labels) : aujourd'hui sans doublon de clés, fragile si un label se répète par casse. À faire converger vers `reference.position_canonical` si le parseur LNR s'active (F06).
- La détection de blessures dépend des seuils F12/F13 : la prévalence 1,6 % et les taux par poste bougeront avec l'annotation F16.
- `m0_global` dans le runner : la référence de skill est le taux global sans lissage ; si M0-position devient la référence officielle, basculer `GlobalRateModel` → `PositionRateModel` dans `runner.py`.


### 2026-11-08 — révision (F20)

- Censure du label en fin de saison découverte en F20 : le runner exclut désormais les lignes
  sans 2 matchs de suivi (`with_label_observability`). M0 par poste refait sur cette base
  (test 2024-25, 7 819 lignes, prévalence 1,71 %) : log-loss 0,0979, Brier 0,01716, skill
  +0,0001 vs global, taux par poste 9,5 (HOOKER) à 33,3 (SCRUM_HALF) /1000 h. Les chiffres
  ci-dessus (8 473 lignes) incluaient ces faux négatifs.
- La ROADMAP n'avait pas été passée à `done` dans le commit F19 : corrigé dans le commit F20.
