-- F17 docs/05 §7 : cibles (futur du match t par construction, jamais des features).
with inj as (
  select player_id, onset_date, onset_match_id, context, days_missed, source_confidence
  from {{ ref('fact_injury_event') }}
  where source_confidence >= {{ var('injury_conf_threshold', 0.6) }}
),
in_match as (
  select
    player_id, onset_match_id as match_id,
    max(source_confidence) as y_injury_conf,
    arg_max(days_missed, source_confidence) as y_days_missed
  from inj where context = 'match' group by player_id, onset_match_id
),
any_7d as (
  select distinct b.player_id, b.match_id
  from {{ ref('int_ml_base') }} b
  join inj i
    on i.player_id = b.player_id
    and i.onset_date >= b.match_date
    and i.onset_date < b.match_date + 7
)
select
  b.player_id,
  b.match_id,
  m.match_id is not null as y_injury,
  a.match_id is not null as y_injury_any_7d,
  m.y_days_missed::integer as y_days_missed,
  m.y_injury_conf
from {{ ref('int_ml_base') }} b
left join in_match m using (player_id, match_id)
left join any_7d a using (player_id, match_id)
