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

- [ ] Extension du parseur allrugby (F05) aux pages Champions Cup / Challenge Cup **ou** utilisation d'ESPN (selon la couverture constatée sur fixtures, décision dans le journal).
- [ ] Calendrier unifié `staging/fixture_calendar` : `competition_code, season_id, round, kickoff_ts, venue_name, home_team_name, away_team_name, source`, alimenté par toutes les sources ; API-Sports en secours si la clé est fournie.
- [ ] Normalisation des noms d'équipes via `data/reference/team_aliases.csv` (créé ici : `raw_name, source, team_canonical, is_national`).
- [ ] Normalisation des stades via `venue_aliases.csv` vers `venues.csv`.
- [ ] Assets Dagster `europe_staging_*`, `calendar_staging`.
- [ ] Fixtures : un match de poule Champions Cup, un quart de finale Challenge Cup, une page calendrier.

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

- [ ] Tous les noms d'équipes des fixtures sont résolus via les alias.
- [ ] Calendrier sans doublon de match (clé naturelle `docs/04-data-model.md` §6).
- [ ] `make check` vert.

## Journal

