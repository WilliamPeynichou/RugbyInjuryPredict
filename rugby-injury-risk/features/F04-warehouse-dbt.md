# F04 — Entrepôt DuckDB et projet dbt

| Champ | Valeur |
|---|---|
| Phase | 1 |
| Dépendances | F02 |
| Estimation | M |
| Docs de référence | `docs/04-data-model.md`, `docs/03-architecture.md` §2.3, `docs/08-conventions.md` §3 |

## Objectif

Initialiser le projet dbt-duckdb, la convention de staging Parquet, les dimensions issues des données de référence et la fonction de pseudonymisation.

## Contexte

Les ingestions (F05+) écrivent du Parquet de staging ; dbt le transforme en marts. La pseudonymisation est posée dès maintenant pour que la table ML (F17) n'ait qu'à l'utiliser.

## Périmètre

- [ ] Ajouter `dbt-core`, `dbt-duckdb`.
- [ ] `dbt/` : `dbt_project.yml`, `profiles.yml` (DuckDB `data/warehouse.duckdb`, extension `parquet`), dossiers `models/{staging,intermediate,marts,ml}`, `seeds/`, `tests/`, `macros/`.
- [ ] Seeds depuis `data/reference/` (lien ou copie générée par `make seeds`) → `ref_positions`, `ref_competitions`, `ref_venues`, `ref_venue_surface`, `ref_test_windows`, `ref_rules_protection`.
- [ ] Marts de dimensions statiques : `dim_competition`, `dim_season` (depuis `config/seasons.yaml` exporté en seed), `dim_venue`, `venue_surface`.
- [ ] Déclaration des `sources` externes Parquet (glob `data/staging/<entity>/**/*.parquet`) pour `match`, `appearance`, `player_profile`, avec un exemple vide pour que `dbt build` passe.
- [ ] `src/rugby_risk/warehouse.py` : `connect()` (DuckDB), `write_staging(df, entity, source, season)` (écriture Parquet partitionnée, schéma validé par Pandera), `upsert(table, df, keys)`.
- [ ] `src/rugby_risk/privacy.py` : `player_key(player_id: int) -> str` = HMAC-SHA256 avec `PSEUDONYM_SALT`, 16 hex ; refuse un sel vide hors env `test`.
- [ ] Macro dbt `player_key(col)` qui appelle la même logique (UDF Python enregistrée dans DuckDB via un hook `on-run-start`, ou table de correspondance générée par Python — choisir et justifier dans le journal).
- [ ] Cible `make dbt` opérationnelle.

## Hors périmètre

- `dim_player`, `fact_match`, `fact_appearance` réels (F09, F10).

## Spécification technique

Schémas Pandera de staging (contrat pour F05–F08) :

```python
class StagingMatch(pa.DataFrameModel):
    source: str; source_match_id: str; competition_code: str; season_id: str
    round: str | None; kickoff_ts: datetime (UTC); venue_name: str | None
    home_team_name: str; away_team_name: str; home_score: int | None; away_score: int | None

class StagingAppearance(pa.DataFrameModel):
    source: str; source_match_id: str; source_player_id: str; player_name: str
    team_name: str; shirt_number: int | None; is_starter: bool
    position_raw: str | None; minutes_played: int | None (0..100)
    yellow_cards: int; red_cards: int

class StagingPlayerProfile(pa.DataFrameModel):
    source: str; source_player_id: str; full_name: str; birth_date: date | None
    height_cm: int | None; weight_kg: int | None; nationality: str | None
    jiff: bool | None; positions_raw: str | None
```

## Fichiers

| Fichier | Action |
|---|---|
| `dbt/**` | créer |
| `src/rugby_risk/{warehouse,privacy}.py`, `src/rugby_risk/staging_schemas.py` | créer |

## Tests

- `tests/unit/test_privacy.py` — déterminisme, sel différent → clé différente, sel vide refusé en `dev`.
- `tests/integration/test_dbt_build.py` — `dbt build` passe sur un staging vide (marqueur `integration`).
- `tests/unit/test_warehouse.py` — `write_staging` rejette un DataFrame non conforme ; `upsert` idempotent (deux fois → mêmes lignes).

## Critères d'acceptation

- [ ] `make dbt` vert sur dépôt vierge.
- [ ] La fonction de pseudonymisation Python et la version dbt produisent la même clé (test).
- [ ] `make check` vert.

## Journal

