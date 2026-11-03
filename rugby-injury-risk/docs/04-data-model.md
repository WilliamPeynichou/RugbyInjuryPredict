# 04 — Modèle de données

Schéma de référence de l'entrepôt DuckDB (marts dbt). Les noms de colonnes sont **contractuels** : toute modification passe par une mise à jour de ce document.

## 1. Vocabulaires contrôlés (`data/reference/`)

### `positions.csv`

| position_code | position_label_fr | position_group | unit | shirt_numbers |
|---|---|---|---|---|
| PROP | Pilier | front_row | forward | 1;3;17;18 |
| HOOKER | Talonneur | front_row | forward | 2;16 |
| LOCK | Deuxième ligne | lock | forward | 4;5;19 |
| BACK_ROW | Troisième ligne | back_row | forward | 6;7;8;20 |
| SCRUM_HALF | Demi de mêlée | half_back | back | 9;21 |
| FLY_HALF | Demi d'ouverture | half_back | back | 10;22 |
| CENTRE | Centre | centre | back | 12;13;23 |
| WING | Ailier | back_three | back | 11;14 |
| FULLBACK | Arrière | back_three | back | 15 |

Les numéros 16–23 sont indicatifs (un banc peut varier) : le poste d'un remplaçant vient d'abord de la source (LNR, allrugby), puis du poste principal du joueur, puis du numéro.

Hiérarchie de modélisation : `position_code` (9) ⊂ `position_group` (6) ⊂ `unit` (2).

### `competitions.csv`

`competition_code` ∈ {`TOP14`, `PROD2`, `CHAMPIONS_CUP`, `CHALLENGE_CUP`, `SIX_NATIONS`, `AUTUMN_TESTS`, `SUMMER_TESTS`, `NATIONS_CHAMPIONSHIP`, `RWC`, `OTHER_TEST`}, avec `level` ∈ {`club_domestic`, `club_europe`, `international`}.

### Autres

`venues.csv`, `venue_surface.csv`, `test_windows.csv`, `protected_players.csv`, `rules_protection.csv`, `er_overrides.csv`, `seasons.csv` (`season_id` au format `2025-2026`, `start_date`, `end_date`, `is_covid_disrupted`).

## 2. Dimensions

```sql
CREATE TABLE dim_player (
  player_id        BIGINT PRIMARY KEY,      -- ID interne stable (séquence)
  player_key       TEXT UNIQUE NOT NULL,    -- pseudonyme : HMAC-SHA256(player_id, PSEUDONYM_SALT), 16 hex
  full_name        TEXT NOT NULL,
  birth_date       DATE,
  height_cm        INTEGER,
  weight_kg        INTEGER,
  nationality      TEXT,
  jiff             BOOLEAN,
  primary_position TEXT REFERENCES ref_positions(position_code),
  position_group   TEXT,
  unit             TEXT
);

CREATE TABLE player_source_xref (
  source            TEXT NOT NULL,
  source_player_id  TEXT NOT NULL,
  player_id         BIGINT NOT NULL REFERENCES dim_player,
  match_confidence  DOUBLE,
  method            TEXT,                   -- anchor_lnr | splink | manual_override
  PRIMARY KEY (source, source_player_id)
);

CREATE TABLE dim_team (
  team_id      INTEGER PRIMARY KEY,
  name         TEXT NOT NULL,
  short_name   TEXT,
  country      TEXT,
  is_national  BOOLEAN NOT NULL
);

CREATE TABLE dim_competition (competition_code TEXT PRIMARY KEY, name TEXT, level TEXT);
CREATE TABLE dim_season (season_id TEXT PRIMARY KEY, start_date DATE, end_date DATE, is_covid_disrupted BOOLEAN);
CREATE TABLE dim_venue (venue_id INTEGER PRIMARY KEY, name TEXT, city TEXT, country TEXT, lat DOUBLE, lon DOUBLE);
CREATE TABLE venue_surface (venue_id INTEGER, season_id TEXT, surface TEXT, PRIMARY KEY (venue_id, season_id)); -- natural | hybrid | synthetic
```

## 3. Faits

```sql
CREATE TABLE fact_match (
  match_id          BIGINT PRIMARY KEY,
  competition_code  TEXT NOT NULL,
  season_id         TEXT NOT NULL,
  round             TEXT,                   -- 'J1'..'J26', 'BARRAGE', 'DEMI', 'FINALE', 'TEST'
  kickoff_ts        TIMESTAMPTZ NOT NULL,   -- UTC
  venue_id          INTEGER,
  home_team_id      INTEGER NOT NULL,
  away_team_id      INTEGER NOT NULL,
  home_score        INTEGER,
  away_score        INTEGER,
  is_playoff        BOOLEAN NOT NULL DEFAULT FALSE,
  source_ids        JSON                    -- {"lnr": "...", "allrugby": "...", "espn": "..."}
);

-- Grain : joueur × match pour lequel il figurait sur la feuille (titulaire ou banc, entré ou non)
CREATE TABLE fact_appearance (
  match_id         BIGINT NOT NULL,
  player_id        BIGINT NOT NULL,
  team_id          INTEGER NOT NULL,
  shirt_number     INTEGER,
  is_starter       BOOLEAN NOT NULL,
  position_played  TEXT,                    -- position_code
  minutes_played   INTEGER NOT NULL,        -- 0 si banc non entré
  minute_on        INTEGER,                 -- 0 si titulaire
  minute_off       INTEGER,                 -- NULL si a fini le match
  off_reason       TEXT NOT NULL DEFAULT 'unknown', -- tactical | injury | hia | card | unknown
  yellow_cards     INTEGER DEFAULT 0,
  red_cards        INTEGER DEFAULT 0,
  primary_source   TEXT NOT NULL,
  PRIMARY KEY (match_id, player_id)
);

-- Grain : joueur × match de son équipe pendant qu'il appartient à l'effectif (joué ou non)
CREATE TABLE fact_eligibility (
  match_id      BIGINT NOT NULL,
  player_id     BIGINT NOT NULL,
  team_id       INTEGER NOT NULL,
  on_sheet      BOOLEAN NOT NULL,
  played        BOOLEAN NOT NULL,           -- minutes_played > 0
  absence_reason TEXT,                      -- NULL si on_sheet ; sinon injury | international_duty | suspension | protected_rest | rotation | unknown
  PRIMARY KEY (match_id, player_id)
);

CREATE TABLE fact_squad_membership (       -- appartenance club × saison (période)
  player_id   BIGINT, team_id INTEGER, season_id TEXT,
  valid_from  DATE, valid_to DATE,
  PRIMARY KEY (player_id, team_id, season_id, valid_from)
);

CREATE TABLE fact_injury_event (
  injury_id          BIGINT PRIMARY KEY,
  player_id          BIGINT NOT NULL,
  onset_date         DATE NOT NULL,
  onset_match_id     BIGINT,                -- NULL si blessure hors match identifié
  context            TEXT NOT NULL,         -- match | training | unknown
  body_region        TEXT,                  -- head | neck | shoulder | arm | trunk | hip_groin | thigh | knee | lower_leg | ankle | foot | other
  injury_type        TEXT,                  -- concussion | ligament | muscle | fracture | contusion | tendon | other | unknown
  is_concussion      BOOLEAN NOT NULL DEFAULT FALSE,
  return_date        DATE,
  days_missed        INTEGER,
  severity_class     TEXT,                  -- minimal_mild (2-7) | moderate (8-28) | severe (>28) | unknown
  censored           BOOLEAN NOT NULL,      -- retour non observé
  source_confidence  DOUBLE NOT NULL,       -- 0..1
  signals            TEXT[],                -- exit | announcement | absence
  evidence           JSON                   -- URLs, extraits courts, ids
);

CREATE TABLE fact_unavailability (
  player_id   BIGINT, start_date DATE, end_date DATE,
  reason      TEXT,                         -- international_duty | suspension | protected_rest | rotation | unknown
  evidence    JSON
);
```

## 4. Table d'apprentissage

```sql
-- Grain : player_key × match d'équipe auquel il était éligible (fact_eligibility), toutes features AS OF kickoff
CREATE TABLE ml_player_match (
  player_key              TEXT NOT NULL,     -- pseudonymisé, jamais player_id ni nom
  match_id                BIGINT NOT NULL,
  season_id               TEXT NOT NULL,
  kickoff_ts              TIMESTAMPTZ NOT NULL,
  as_of_ts                TIMESTAMPTZ NOT NULL,  -- = kickoff_ts - 1 seconde
  competition_code        TEXT,
  position_code           TEXT, position_group TEXT, unit TEXT,
  -- exposition et cible
  played                  BOOLEAN,
  minutes_played          INTEGER,           -- exposition du match t (offset), PAS une feature
  y_injury                BOOLEAN,           -- blessure en match lors du match t
  y_injury_conf           DOUBLE,            -- confiance de l'épisode, NULL si y_injury = false
  y_days_missed           INTEGER,
  -- features : voir 05-features-spec.md
  ...
  dataset_version         TEXT NOT NULL,
  PRIMARY KEY (player_key, match_id)
);
```

`minutes_played`, `played`, `y_*` sont des **colonnes cibles ou d'exposition** : elles sont listées dans `TARGET_AND_EXPOSURE_COLUMNS` (F17) et interdites dans les matrices de features.

## 5. Tables Supabase (service, agrégées uniquement)

```sql
pred_position_curve (model_version, season_id, position_code, n_consecutive, scenario, p_mean, p_low90, p_high90, n_players_support, computed_at)
pred_position_season (model_version, season_id, position_code, incidence_per_1000h, injuries_count_bucket, exposure_hours, computed_at)
calibration_public (model_version, test_season, position_group, bin, p_pred_mean, p_obs, n)
model_registry_public (model_version, trained_at, train_seasons, test_season, brier, brier_skill, logloss, calib_slope, notes)
```

Garde-fou : toute ligne avec `n_players_support < 10` est supprimée avant export (F25).

## 6. Règles de clés et d'idempotence

| Table | Clé naturelle d'upsert |
|---|---|
| `fact_match` | (`competition_code`, `season_id`, `home_team_id`, `away_team_id`, date(`kickoff_ts`)) |
| `fact_appearance` | (`match_id`, `player_id`) |
| `fact_injury_event` | (`player_id`, `onset_date`, `body_region`) — fusion si chevauchement < 7 jours |
| `player_source_xref` | (`source`, `source_player_id`) |
