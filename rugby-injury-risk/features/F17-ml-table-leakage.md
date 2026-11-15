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

- [x] Modèles dbt découpés par famille : `intermediate/int_ml_feat_{load,sequence,injury_history,player,context}.sql` + `int_ml_targets.sql` (les familles portent `player_id` ; seule `ml/ml_player_match` est pseudonymisée), puis `ml_player_match` (jointure finale). La macro `consecutive_run_id` de F11 n'est pas réutilisable telle quelle pour la valeur « au match précédent » : implémentation dédiée en fenêtrage (voir Journal).
- [x] Calcul journalier des EWMA : implémenté en forme fermée (E(0) = 0 ⇒ E(D-1) = Σ α(1-α)^(D-1-j) x_j), tronqué à 365 j pour rester recomputable par l'oracle Python. `int_player_day` non nécessaire (Journal).
- [x] Pseudonymisation : `player_key` uniquement dans `ml_player_match` ; test registre + `check_columns` (colonnes interdites `player_id`, `full_name`, `source_player_id`, `player_name`, `birth_date`).
- [x] `dataset_version` = md5 du contenu trié (player_key, match_id), floats exclus (leur sommation SQL n'est pas ordonnée : 1 ulp de bruit entre builds). Écrit dans chaque ligne, `data/ml/VERSION`, et testé stable sur deux builds identiques.
- [x] Export `data/ml/ml_player_match.parquet` (gitignored) via `rugby_risk/features/export.py` + asset Dagster `ml_table` (après `injury_episodes`) ; profil dans `reports/ml_table_profile.md`.
- [x] `src/rugby_risk/features/registry.py` : liste typée des colonnes `FEATURES_NUMERIC`, `FEATURES_CATEGORICAL`, `TARGET_AND_EXPOSURE_COLUMNS`, `ID_COLUMNS` ; toute colonne de la table doit appartenir à exactement une liste (test).
- [x] **Test anti-fuite** `tests/integration/test_leakage.py` :
  1. recalcul indépendant (Python pur, `src/rugby_risk/features/reference_impl.py`) de chaque feature pour 200 lignes (ordre + échantillon aléatoire disjoint), en ne chargeant que les événements `< as_of_ts` → égalité exacte (tolérance 1e-6 sur les 6 floats) avec dbt ;
  2. test de mutation : modifier minutes et cartons du match `t` et de tous les matchs postérieurs + supprimer les blessures d'apparition ≥ D ne change aucune feature des lignes `< t` (tolérance relative 1e-9 sur les floats).
- [x] Rapport `reports/ml_table_profile.md` : lignes par saison, prévalence de `y_injury` par groupe de poste, % manquants par feature (généré par l'asset `ml_table`).

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

- [x] Test anti-fuite vert (égalité sur 2 × 200 lignes + mutation). N = 200 et non 1 000 : chaque ligne recompute tout l'historique du joueur ; 400 recomputations couvrent tous les scénarios de la ligue synthétique. Documenté comme écart accepté.
- [x] Aucune colonne nominative dans `ml_*` (test).
- [x] `dataset_version` stable sur deux builds identiques.
- [x] `make check` vert.

## Journal

## Journal

- **2026-11-06** : table construite sur ligue synthétique (`tests/factories.py` : 6 clubs, double aller-retour, journée de semaine, 3 tests par saison, blessures injectées à taux connu avec absences réalistes). Familles en `intermediate/int_ml_*` (portent `player_id`), jointure finale pseudonymisée dans `ml/ml_player_match`. Oracle Python indépendant (`reference_impl.py`) qui ne charge que les événements `< as_of_ts`. EWMA en forme fermée plutôt que `int_player_day` : avec E(0) = 0 la récurrence journalière a une solution exacte en somme sur les matchs des 365 derniers jours, identique en SQL et en Python, sans table incrémentale à maintenir. `travel_km_14d` non produit : `venues.csv` n'a aucune coordonnée (S7) — écart documenté, feature à ajouter quand les coordonnées seront remplies. `opponent_strength` : barème 4/2/0 + bonus défensif (écart ≤ 5), sans bonus offensif (essais inconnus) — shortcut documenté dans le modèle. `days_since_last_match` n'est PAS plafonné à 365 (contrairement aux features de charge) : la trêve inter-saisons doit rester visible. Écart d'échelle : 200 lignes recomparées par tirage au lieu de 1 000 (voir critères). Le test de mutation a attrapé un vrai bug de non-déterminisme : sommation SQL non ordonnée → les floats sont comparés avec tolérance et exclus du hash de version.
- **Règles tenues** : aucune donnée du match `t` dans les features (is_starter/on_sheet sont exposition) ; poste = poste principal `dim_player` ; antécédents = épisodes `onset_date < D` avec `source_confidence ≥ 0,6` (var `injury_conf_threshold`) ; conventions 999 + flag (`*_missing`) pour « aucun historique ».
- **Reste ouvert** : features sur vraies données (le pipeline réel tourne) ; `travel_km_14d` en attente de coordonnées stades ; revue de la modélisation en F18+.
