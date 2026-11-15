-- Un match par clé naturelle : calendrier unifié F08 + scores et ids sources (int_match__reconciled).
with cal as (
  select
    *,
    {{ stable_id("concat_ws('|', competition_code, season_id, home_team_name, away_team_name, "
      ~ utc_date('kickoff_ts') ~ ")") }} as match_id
  from {{ ref('stg_fixture_calendar') }}
),
src as (
  select
    match_id,
    arg_min(home_score, priority) filter (where home_score is not null) as home_score,
    arg_min(away_score, priority) filter (where away_score is not null) as away_score,
    json_group_object(source, source_match_id) as source_ids
  from {{ ref('int_match__reconciled') }}
  group by match_id
)
select
  cal.match_id,
  cal.competition_code,
  cal.season_id,
  cal.round,
  cal.kickoff_ts,
  cal.venue_id::integer as venue_id,
  h.team_id as home_team_id,
  a.team_id as away_team_id,
  src.home_score::integer as home_score,
  src.away_score::integer as away_score,
  -- shortcut: libellés de phase bruts (LNR, allrugby, ESPN) ; à remplacer par un vocabulaire contrôlé.
  coalesce(regexp_matches(lower(cal.round), 'barrage|demi|final|quart|quarter|semi|play'), false)
    as is_playoff,
  src.source_ids
from cal
join {{ ref('dim_team') }} h on h.name = cal.home_team_name
join {{ ref('dim_team') }} a on a.name = cal.away_team_name
left join src using (match_id)
