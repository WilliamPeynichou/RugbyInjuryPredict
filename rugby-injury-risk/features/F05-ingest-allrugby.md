# F05 — Ingestion allrugby (minutes et profils)

| Champ | Valeur |
|---|---|
| Phase | 1 |
| Dépendances | F03, F04 |
| Estimation | L |
| Docs de référence | `docs/01-data-sources.md` §1, §3, `docs/04-data-model.md` (contrats staging), `docs/03-architecture.md` §2.1–2.2 |

## Objectif

Collecter et parser, pour le Top 14 depuis 2013-14, les feuilles de match (titulaires, banc, minutes, cartons) et les profils joueurs d'allrugby, en staging Parquet. Introduire Dagster avec les premiers assets partitionnés.

## Contexte

allrugby est la source primaire des minutes. Le développement se fait **entièrement sur fixtures** : l'exécution réelle n'est possible qu'une fois `authorized: true` (décision humaine).

## Périmètre

- [ ] `sources/allrugby/urls.py` : URL des pages compétition-saison, match, joueur.
- [ ] `sources/allrugby/fetch.py` : découverte des matchs d'une saison (page calendrier/résultats) → pages de match → pages joueurs rencontrés (une fois par joueur et par saison).
- [ ] `parsers/allrugby/{match,player}.py` : `parse_match(html) -> (StagingMatch, list[StagingAppearance])`, `parse_player(html) -> StagingPlayerProfile`.
- [ ] Règles : n° 1–15 → `is_starter = True` ; 16–23 → banc ; minutes absentes pour un remplaçant non entré → 0 ; cartons.
- [ ] Ajouter `dagster`, `dagster-webserver`. `orchestration/definitions.py` avec `StaticPartitionsDefinition` des saisons (depuis `config/seasons.yaml`) et assets : `allrugby_raw_pages` → `allrugby_staging_matches`, `allrugby_staging_appearances`, `allrugby_staging_profiles`.
- [ ] Les assets de staging se recalculent depuis le lac (`offline=True`) sans réseau.
- [ ] Capturer **au moins 6 fixtures** réelles figées (si l'accès est autorisé ; sinon fixtures construites à la main au format observé, signalé dans le journal) : match standard, match avec carton rouge, match avec remplaçant non entré, match de phase finale, profil complet, profil incomplet.

## Hors périmètre

- Pro D2, coupes d'Europe, tests (F07, F08). Résolution d'entités (F09).

## Spécification technique

- Identifiant source joueur : l'entier final du slug `/{slug}-{id}.html`.
- Identifiant source match : identifiant présent dans l'URL du match.
- `kickoff_ts` : date + heure locale Europe/Paris convertie en UTC ; si heure absente, 15:00 locale + flag `kickoff_time_imputed` (ajouter la colonne au contrat staging via F04 si nécessaire, noter dans le journal).
- Contrôle de cohérence intégré au parseur : 15 titulaires par équipe, sinon enregistrement en quarantaine avec raison.
- `PARSER_VERSION = "allrugby-1"`.

## Fichiers

| Fichier | Action |
|---|---|
| `src/rugby_risk/sources/allrugby/{__init__,urls,fetch}.py` | créer |
| `src/rugby_risk/parsers/allrugby/{__init__,match,player}.py` | créer |
| `orchestration/{__init__,definitions,partitions}.py`, `orchestration/assets/allrugby.py` | créer |
| `tests/fixtures/allrugby/*` + `README.md` | créer |

## Tests

- `tests/unit/parsers/test_allrugby_match.py` — chaque fixture : nombre de titulaires, minutes d'un joueur connu, banc non entré à 0, carton rouge.
- `tests/unit/parsers/test_allrugby_player.py` — champs du profil, profil incomplet sans exception.
- `tests/integration/test_allrugby_assets.py` — matérialisation des assets sur un lac de fixtures (offline) → Parquet conforme au schéma ; rematérialisation → mêmes lignes (idempotence).

## Critères d'acceptation

- [ ] `uv run dagster asset materialize --select allrugby_staging_* --partition 2023-2024` fonctionne en offline sur fixtures.
- [ ] Aucun appel réseau dans la suite de tests.
- [ ] La source étant non autorisée, un lancement réel échoue proprement avec `SourceNotAuthorizedError`.
- [ ] `make check` vert.

## Journal

