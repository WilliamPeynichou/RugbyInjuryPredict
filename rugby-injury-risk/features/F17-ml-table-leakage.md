# F17 — Table ml_player_match et test anti-fuite

| Champ | Valeur |
|---|---|
| Phase | 4 |
| Dépendances | F16 |
| Estimation | L |
| Docs de référence | `docs/05-features-spec.md` (intégralité), `docs/04-data-model.md` §4, `docs/07-legal-rgpd.md` §2, `CLAUDE.md` règles 1 et 3 |

## Objectif

Matérialiser la table d'apprentissage `ml_player_match` (une ligne par joueur éligible × match), pseudonymisée, avec toutes les features de `05-features-spec.md` calculées **as of** le coup d'envoi, et prouver l'absence de fuite.

## Contexte

C'est l'interface unique entre l'entrepôt et la modélisation. Tous les modèles (F19–F24) lisent cette table et rien d'autre.

## Périmètre

- [ ] Modèles dbt `dbt/models/ml/` découpés par famille : `ml_feat_load`, `ml_feat_sequence` (macro `consecutive_run_id` de F11), `ml_feat_international`, `ml_feat_injury_history`, `ml_feat_player`, `ml_feat_context`, `ml_targets`, puis `ml_player_match` (jointure finale).
- [ ] Calcul journalier des EWMA via une table calendrier joueur × jour (`int_player_day`), matérialisée en incrémental.
- [ ] Pseudonymisation : `player_key` uniquement ; aucune colonne `player_id`, `full_name`, `source_player_id` dans `ml_*` (test).
- [ ] `dataset_version` = hash du contenu (DuckDB `md5` sur un tri stable) écrit dans chaque ligne et dans `data/ml/VERSION`.
- [ ] Export `data/ml/ml_player_match.parquet` (gitignored) pour la modélisation.
- [ ] `src/rugby_risk/features/registry.py` : liste typée des colonnes `FEATURES_NUMERIC`, `FEATURES_CATEGORICAL`, `TARGET_AND_EXPOSURE_COLUMNS`, `ID_COLUMNS` ; toute colonne de la table doit appartenir à exactement une liste (test).
- [ ] **Test anti-fuite** `tests/integration/test_leakage.py` :
  1. recalcul indépendant (Python pur, implémentation de référence dans `src/rugby_risk/features/reference_impl.py`) de chaque feature pour 1 000 lignes tirées au hasard, en ne chargeant que les événements `< as_of_ts` → égalité exacte avec dbt ;
  2. test de mutation : modifier les minutes et cartons du match `t` et des matchs postérieurs ne change aucune feature de la ligne `t`.
- [ ] Rapport `reports/ml_table_profile.md` : nombre de lignes par saison, prévalence de `y_injury` par poste, taux de valeurs manquantes par feature.

## Hors périmètre

- Modèles. Sélection de features.

## Spécification technique

- `as_of_ts = kickoff_ts - interval 1 second`.
- Antécédents de blessure : seuls les épisodes avec `onset_date < date(kickoff_ts)` et `source_confidence ≥ var('injury_conf_threshold', 0.6)`. Pour `days_missed_365d`, seuls les épisodes dont `return_date < date(kickoff_ts)` (sinon jours écoulés jusqu'à `D`).
- Valeurs « aucun événement » : 999 + colonne booléenne `<feature>_missing` quand c'est pertinent (documenté dans le registre).

## Fichiers

| Fichier | Action |
|---|---|
| `dbt/models/ml/*.sql` + `.yml`, `dbt/models/intermediate/int_player_day.sql` | créer |
| `src/rugby_risk/features/{__init__,registry,reference_impl,export}.py` | créer |
| `tests/integration/test_leakage.py`, `tests/unit/features/test_registry.py` | créer |
| `tests/factories.py` (générateur de saisons synthétiques avec blessures à taux connus) | créer |

## Tests

- Test anti-fuite (ci-dessus).
- `tests/unit/features/test_registry.py` — partition exacte des colonnes ; aucune colonne interdite.
- `tests/unit/features/test_reference_impl.py` — cas à la main : `consecutive_matches`, `min_28d`, `days_since_last_match`, `short_turnaround`, `intl_window`, antécédents.
- `tests/integration/test_ml_table_synthetic.py` — sur `factories.make_league(seasons=3, seed=1)`, la table a le nombre de lignes attendu et la prévalence injectée (± 10 %).

## Critères d'acceptation

- [ ] Test anti-fuite vert (égalité exacte sur 1 000 lignes + mutation).
- [ ] Aucune colonne nominative dans `ml_*` (test).
- [ ] `dataset_version` stable sur deux builds identiques.
- [ ] `make check` vert.

## Journal

