"""Pandera contracts for Parquet staging (F05-F08 write them, dbt reads them)."""

import pandera.polars as pa
import polars as pl


class StagingMatch(pa.DataFrameModel):
    source: pl.String
    source_match_id: pl.String
    competition_code: pl.String
    season_id: pl.String
    round: pl.String = pa.Field(nullable=True)
    kickoff_ts: pl.Datetime(time_zone="UTC")  # type: ignore[valid-type]
    kickoff_time_imputed: pl.Boolean
    venue_name: pl.String = pa.Field(nullable=True)
    home_team_name: pl.String
    away_team_name: pl.String
    home_score: pl.Int64 = pa.Field(nullable=True)
    away_score: pl.Int64 = pa.Field(nullable=True)


class StagingAppearance(pa.DataFrameModel):
    source: pl.String
    source_match_id: pl.String
    source_player_id: pl.String
    player_name: pl.String
    team_name: pl.String
    shirt_number: pl.Int64 = pa.Field(nullable=True)
    is_starter: pl.Boolean
    position_raw: pl.String = pa.Field(nullable=True)
    minutes_played: pl.Int64 = pa.Field(nullable=True, ge=0, le=100)
    yellow_cards: pl.Int64
    red_cards: pl.Int64


class StagingPlayerProfile(pa.DataFrameModel):
    source: pl.String
    source_player_id: pl.String
    full_name: pl.String
    birth_date: pl.Date = pa.Field(nullable=True)
    height_cm: pl.Int64 = pa.Field(nullable=True)
    weight_kg: pl.Int64 = pa.Field(nullable=True)
    nationality: pl.String = pa.Field(nullable=True)
    jiff: pl.Boolean = pa.Field(nullable=True)
    positions_raw: pl.String = pa.Field(nullable=True)


SCHEMAS = {
    "match": StagingMatch,
    "appearance": StagingAppearance,
    "player_profile": StagingPlayerProfile,
}
