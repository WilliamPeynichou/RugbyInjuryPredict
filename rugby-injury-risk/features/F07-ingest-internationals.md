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

- [x] `sources/worldrugby/` : liste des matchs par période et équipe, détail d'un match (compositions, remplacements, minutes).
- [x] `sources/espn/` : client JSON `summary?event=` en secours (lineups), utile aussi pour F08.
- [x] Parseurs JSON → `StagingMatch` (`competition_code` mappé sur `competitions.csv`) et `StagingAppearance` avec minutes. Si seules les minutes d'entrée/sortie existent, calcul `minutes_played`.
- [x] Asset Dagster `intl_staging_*` partitionné par saison.
- [x] Recoupement : pour chaque match présent dans les deux sources, comparer le total des minutes par équipe ; écart > 5 % → rapport.
- [x] Fixtures : un match de Six Nations, un test de novembre, un match de Coupe du monde, un JSON incomplet (lineups manquants).

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

- [x] Les 4 fixtures sont parsées ou mises en quarantaine avec raison explicite.
- [x] Tout `competition_code` produit existe dans `competitions.csv`.
- [x] `make check` vert.

## Journal

- Formes JSON reprises de dépôts publics cités par le document de recherche, sans appel aux API : World Rugby d'après `bpcsaund/rugby-analytics` (`/rugby/v3/match`, `/match/{altId}/summary`, `/match/{altId}/timeline`) ; ESPN d'après `transientlunatic/Rugby-Data` (`/{league}/scoreboard`, `/{league}/summary?event=`). Endpoints et exemples anonymisés dans `sources/{worldrugby,espn}/README.md`.
- `espn` et `worldrugby` restent `authorized: false` : code live gardé par F03, aucun appel réel. Fixtures JSON générées par `tests/fixtures/worldrugby/build_fixtures.py` (joueurs fictifs).
- Minutes World Rugby : `Sub On`/`Sub Off` explicites ; `IR`/`HIAO` = bascule d'état (les deux joueurs sont marqués au même instant) ; `Red Card` = sortie définitive ; fin de match = max(80', dernier événement), plafonné à 100'. Sans timeline → `minutes_played = NULL`.
- **Écart** : ESPN ne donne pas les minutes (`NULL`, titulaire = maillot 1–15, drapeau `starter` ignoré, cartons non lus). Le recoupement « minutes par équipe entre sources » est donc fait ainsi : minutes World Rugby comparées à 15 × 80 (écart > 5 % signalé) et effectif de la feuille comparé à ESPN pour les matchs présents dans les deux sources (jointure date + équipes). Rapport : `data/staging/_reports/intl_minutes/season=*.parquet`, colonne `flagged`.
- Compétitions : `data/reference/competition_aliases.csv` (sous-chaîne → code). Libellé générique → mois (oct.–déc. `AUTUMN_TESTS`, juin–août `SUMMER_TESTS`, sinon `OTHER_TEST`). Exclus (quarantaine « Hors périmètre ») : féminin, 7, U18/U19/U20. Le Rugby Championship tombe dans le repli par mois (pas de code dédié dans `competitions.csv`).
- Saison d'un match = intervalle de `config/seasons.yaml` contenant sa date ; le lac n'étant pas partitionné, chaque asset filtre sur la partition demandée.
- Ids ligues ESPN hors Top 14 (`180659`, `164205`, `289234`) non vérifiés : à confirmer au premier appel autorisé.
- ROADMAP : statuts F03, F05, F06 corrigés en `done` (oubli des tours précédents).

- `make check` vert : 131 tests, couverture 91,84 %. CI distante non exécutée. Aucun appel réel aux API.
