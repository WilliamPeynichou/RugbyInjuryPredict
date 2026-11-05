# F08 — Ingestion coupes d'Europe et calendrier

| Champ | Valeur |
|---|---|
| Phase | 2 |
| Dépendances | F03, F04 |
| Estimation | M |
| Docs de référence | `docs/01-data-sources.md` §1, §5, `docs/04-data-model.md` (`fact_match`) |

## Objectif

Compléter la charge de club avec la Champions Cup et la Challenge Cup (matchs des clubs de Top 14), et constituer un calendrier fiable (coups d'envoi, stades) pour toutes les compétitions.

## Contexte

Les doublons Top 14 / coupe d'Europe et les semaines sans repos viennent souvent des coupes. Sans elles, `consecutive_matches` et `days_since_last_match` sont faux.

## Périmètre

- [x] Extension du parseur allrugby (F05) aux pages Champions Cup / Challenge Cup **ou** utilisation d'ESPN (selon la couverture constatée sur fixtures, décision dans le journal).
- [x] Calendrier unifié `staging/fixture_calendar` : `competition_code, season_id, round, kickoff_ts, venue_name, home_team_name, away_team_name, source`, alimenté par toutes les sources ; API-Sports en secours si la clé est fournie (clé absente : rang de priorité réservé, client non écrit).
- [x] Normalisation des noms d'équipes via `data/reference/team_aliases.csv` (créé ici : `raw_name, source, team_canonical, is_national`).
- [x] Normalisation des stades via `venue_aliases.csv` vers `venues.csv`.
- [x] Assets Dagster `europe_staging_*`, `calendar_staging`.
- [x] Fixtures : un match de poule Champions Cup, un quart de finale Challenge Cup, une page calendrier.

## Hors périmètre

- Clubs non Top 14 sauf comme adversaires (on garde leurs matchs contre des clubs de Top 14).

## Spécification technique

Règle de priorité des sources pour `kickoff_ts` : LNR > allrugby > ESPN > API-Sports. Conflit > 2 heures entre deux sources → rapport.

## Fichiers

| Fichier | Action |
|---|---|
| `src/rugby_risk/parsers/allrugby/` ou `parsers/espn/` (extension) | modifier |
| `src/rugby_risk/sources/apisports/*` (optionnel) | créer |
| `orchestration/assets/{europe,calendar}.py` | créer |
| `data/reference/{team_aliases,venue_aliases}.csv` | créer |

## Tests

- `tests/unit/parsers/test_europe.py` — compétition, phase, équipes normalisées.
- `tests/unit/test_aliases.py` — tout alias pointe vers une équipe ou un stade connu ; pas de doublon d'alias.
- `tests/integration/test_calendar.py` — priorité des sources respectée ; conflit rapporté.

## Critères d'acceptation

- [x] Tous les noms d'équipes des fixtures sont résolus via les alias.
- [x] Calendrier sans doublon de match (clé naturelle `docs/04-data-model.md` §6).
- [x] `make check` vert.

## Journal

- **Décision coupes d'Europe : ESPN** (pas allrugby). Le parseur `summary` existe (F07) et couvre les deux coupes avec compositions ; le parseur allrugby est verrouillé sur le Top 14. `parsers/espn/europe.py::parse_europe` = `parse_summary` + filtre : compétition `CHAMPIONS_CUP`/`CHALLENGE_CUP` et au moins un club français (depuis 2014, les clubs français engagés viennent du Top 14). Hors filtre → ignoré (pas de quarantaine) ; JSON invalide → quarantaine.
- Ids ligues ESPN `271937` (Champions Cup) et `272073` (Challenge Cup) non vérifiés : `espn` reste `authorized: false`. Alias `competition_aliases.csv` : `Champions Cup`, `Challenge Cup`, `Top 14`.
- Phase (`round`) : `competitions[0].notes[0].headline` (phases finales) sinon `week.number` → `R<n>`. Champs repris de payloads publics, non vérifiés (shortcut commenté).
- `intl_staging_espn` ne garde plus que les compétitions de niveau `international` ; les coupes vont dans `europe_staging_espn`, écrit sous `staging/match/source=espn_europe/` (colonne `source` = `espn`) pour ne pas écraser le `part.parquet` des internationaux.
- Page calendrier = `scoreboard` ESPN (`parsers/espn/scoreboard.py`) : tous les matchs d'une ligue, joués ou non, scores `NULL`.
- `team_aliases.csv` : colonne `country` ajoutée (nécessaire au filtre « club du Top 14 »). Recherche `(source, raw_name)` puis `(*, raw_name)`. Chaque équipe canonique a son alias `*` ; identité (pays, sélection) unique par équipe, contrôlée au chargement. Noms ESPN des clubs (`Toulouse`, `Clermont Auvergne`…) : supposés, à confirmer au premier appel.
- `venue_aliases.csv` : `raw_name, venue_id` (id plutôt que nom : `venues.csv` a deux « Stade Yves-du-Manoir »). Stade 25 `Matmut Atlantique` ajouté (finales à Bordeaux). Nom inconnu → `venue_id` NULL.
- `calendar_staging` : lit `staging/match/source=*/season=<s>` + les pages `scoreboard` du lac, normalise équipes et stades, une ligne par clé naturelle (`competition_code, season_id, home, away, date(kickoff_ts)` UTC). Priorité `kickoff_ts` : LNR > allrugby > World Rugby > ESPN > API-Sports (World Rugby inséré : source officielle des tests). **Une heure imputée (allrugby 15:00) perd toujours contre une heure observée.** Autres colonnes : première valeur non nulle dans l'ordre de priorité. Conflits (> 2 h entre heures observées) → `data/staging/_reports/calendar_conflicts/season=*.parquet`. Équipes sans alias : warning + métadonnée `unresolved_teams`.
- API-Sports non écrit : aucune clé fournie (souci S9). Le rang `apisports` est réservé dans la priorité.

- `make check` vert : 144 tests, couverture 92,23 %. Aucun appel réel aux API.

