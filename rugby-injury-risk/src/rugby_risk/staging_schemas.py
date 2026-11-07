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


class StagingFixture(pa.DataFrameModel):
    """Unified calendar: one row per match (natural key docs/04 §6), canonical team names."""

    competition_code: pl.String
    season_id: pl.String
    round: pl.String = pa.Field(nullable=True)
    kickoff_ts: pl.Datetime(time_zone="UTC")  # type: ignore[valid-type]
    kickoff_time_imputed: pl.Boolean
    venue_name: pl.String = pa.Field(nullable=True)
    venue_id: pl.Int64 = pa.Field(nullable=True)
    home_team_name: pl.String
    away_team_name: pl.String
    source: pl.String


class StagingNewsDoc(pa.DataFrameModel):
    """Press document (input of F15; produced by F14 when authorized)."""

    doc_id: pl.String
    url: pl.String
    published_at: pl.Datetime(time_zone="UTC")  # type: ignore[valid-type]
    title: pl.String = pa.Field(nullable=True)
    text: pl.String


class StagingInjuryMention(pa.DataFrameModel):
    """Structured injury mention extracted from a press document (F15)."""

    mention_id: pl.String
    doc_id: pl.String
    player_name: pl.String
    team_name: pl.String = pa.Field(nullable=True)
    player_id: pl.Int64 = pa.Field(nullable=True)
    match_id: pl.Int64 = pa.Field(nullable=True)
    onset_date: pl.Date = pa.Field(nullable=True)
    onset_context: pl.String
    body_region: pl.String = pa.Field(nullable=True)
    injury_type: pl.String = pa.Field(nullable=True)
    is_concussion: pl.Boolean
    announced_duration_days_min: pl.Int64 = pa.Field(nullable=True)
    announced_duration_days_max: pl.Int64 = pa.Field(nullable=True)
    season_ending: pl.Boolean
    return_mentioned: pl.Boolean
    quote: pl.String = pa.Field(nullable=True)
    needs_review: pl.Boolean
    extraction_model: pl.String
    prompt_version: pl.String
    extracted_at: pl.Datetime(time_zone="UTC")  # type: ignore[valid-type]


class StagingInjuryEpisode(pa.DataFrameModel):
    """Fused injury episodes (F16), written by the injury_episodes asset (source=fusion)."""

    player_id: pl.Int64
    onset_date: pl.Date = pa.Field(nullable=True)
    onset_match_id: pl.Int64 = pa.Field(nullable=True)
    context: pl.String = pa.Field(nullable=True)
    body_region: pl.String = pa.Field(nullable=True)
    injury_type: pl.String = pa.Field(nullable=True)
    is_concussion: pl.Boolean = pa.Field(nullable=True)
    return_date: pl.Date = pa.Field(nullable=True)
    days_missed: pl.Int64 = pa.Field(nullable=True)
    severity_class: pl.String = pa.Field(nullable=True)
    censored: pl.Boolean = pa.Field(nullable=True)
    source_confidence: pl.Float64 = pa.Field(nullable=True, ge=0.0, le=1.0)
    signals: pl.String
    evidence: pl.String


SCHEMAS = {
    "match": StagingMatch,
    "appearance": StagingAppearance,
    "player_profile": StagingPlayerProfile,
    "fixture_calendar": StagingFixture,
    "news_doc": StagingNewsDoc,
    "injury_mention": StagingInjuryMention,
    "injury_episode": StagingInjuryEpisode,
}
