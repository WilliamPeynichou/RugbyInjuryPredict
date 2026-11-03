# F07 — Ingestion des matchs internationaux

| Champ | Valeur |
|---|---|
| Phase | 2 |
| Dépendances | F03, F04 |
| Estimation | M |
| Docs de référence | `docs/01-data-sources.md` §1 (worldrugby, espn), `docs/05-features-spec.md` §3 |

## Objectif

Collecter les matchs internationaux (Six Nations, tests de novembre / Nations Championship, tournées d'été, Coupe du monde) avec les minutes par joueur, pour les nations dont des joueurs évoluent en Top 14.

## Contexte

La charge internationale est une composante clé de l'enchaînement. Les joueurs étrangers du Top 14 jouent aussi pour leur sélection : on couvre au minimum France, Angleterre, Irlande, Écosse, Pays de Galles, Italie, Afrique du Sud, Nouvelle-Zélande, Australie, Argentine, Fidji, Samoa, Tonga, Géorgie, Japon.

## Périmètre

- [ ] `sources/worldrugby/` : liste des matchs par période et équipe, détail d'un match (compositions, remplacements, minutes).
- [ ] `sources/espn/` : client JSON `summary?event=` en secours (lineups), utile aussi pour F08.
- [ ] Parseurs JSON → `StagingMatch` (`competition_code` mappé sur `competitions.csv`) et `StagingAppearance` avec minutes. Si seules les minutes d'entrée/sortie existent, calcul `minutes_played`.
- [ ] Asset Dagster `intl_staging_*` partitionné par saison.
- [ ] Recoupement : pour chaque match présent dans les deux sources, comparer le total des minutes par équipe ; écart > 5 % → rapport.
- [ ] Fixtures : un match de Six Nations, un test de novembre, un match de Coupe du monde, un JSON incomplet (lineups manquants).

## Hors périmètre

- Matchs internationaux de jeunes, rugby à 7, matchs féminins.

## Spécification technique

- `source_match_id` World Rugby (identifiant de match de l'API) ; `source_player_id` World Rugby (identifiant joueur).
- Mapping des noms d'événements vers `competition_code` dans `data/reference/competition_aliases.csv` (créé ici).
- `PARSER_VERSION = "worldrugby-1"`, `"espn-1"`.
- Les endpoints exacts sont documentés dans `sources/<s>/README.md` avec un exemple de réponse anonymisé.

## Fichiers

| Fichier | Action |
|---|---|
| `src/rugby_risk/sources/{worldrugby,espn}/*`, `src/rugby_risk/parsers/{worldrugby,espn}/*` | créer |
| `orchestration/assets/internationals.py` | créer |
| `data/reference/competition_aliases.csv` | créer |
| `tests/fixtures/{worldrugby,espn}/*` | créer |

## Tests

- `tests/unit/parsers/test_worldrugby.py` — minutes reconstruites, compétition mappée, JSON incomplet → quarantaine.
- `tests/unit/parsers/test_espn.py` — lineups, remplaçants.
- `tests/integration/test_intl_assets.py` — idempotence.

## Critères d'acceptation

- [ ] Les 4 fixtures sont parsées ou mises en quarantaine avec raison explicite.
- [ ] Tout `competition_code` produit existe dans `competitions.csv`.
- [ ] `make check` vert.

## Journal

