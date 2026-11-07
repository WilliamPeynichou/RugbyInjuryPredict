-- F17 docs/05 §1-3 : charge, repos, international, sur les matchs < D (fenêtre 365 j).
-- EWMA journalière (minutes = 0 les jours sans match, E(0) = 0) en forme fermée :
-- E(D-1) = somme alpha * (1 - alpha)^(D-1-j) * x_j, (1 - alpha) = 0.5^(1/demi-vie).
with pairs as (
  select
    b.player_id, b.match_id, b.match_date as d, b.season_id,
    h.match_date as h_date, h.level, h.played, h.minutes, h.gap_days
  from {{ ref('int_ml_base') }} b
  join {{ ref('int_ml_base') }} h
    on h.player_id = b.player_id
    and h.on_sheet
    and h.match_date < b.match_date
    and h.match_date >= b.match_date - 365
),
agg as (
  select
    p.player_id, p.match_id,
    {% for k in [7, 14, 28, 56, 365] -%}
    sum(minutes) filter (where h_date >= d - {{ k }})::integer as min_{{ k }}d,
    {% endfor -%}
    sum(minutes) filter (where h_date >= d - 56 and level = 'international')::integer
      as min_intl_56d,
    sum(minutes) filter (where h_date >= d - 28 and level in ('club_domestic', 'club_europe'))
      ::integer as min_club_28d,
    count(*) filter (where minutes >= 20)::integer as apps_20min_365d,
    sum(minutes) filter (where h_date >= d - 30) / 80.0 as fge_30d,
    {% for name, hl in [('ewma_acute', 7), ('ewma_chronic', 28)] -%}
    sum(minutes * (1 - pow(0.5, 1 / {{ hl }})) * pow(0.5, (d - h_date - 1) / {{ hl }}))
      as {{ name }},
    {% endfor -%}
    sum(minutes) filter (where h_date >= s.start_date)::integer as season_minutes,
    max(h_date) filter (where played) as last_played,
    count(*) filter (where played and h_date >= d - 28 and gap_days < 5)::integer
      as n_short_turnarounds_28d,
    max(h_date) filter (where played and level = 'international') as last_test,
    count(*) filter (where played and level = 'international')::integer as intl_caps_365d
  from pairs p
  join {{ ref('ref_seasons') }} s using (season_id)
  group by p.player_id, p.match_id
),
weeks as (
  -- Semaines pleines [D-7i, D-7(i-1)) avec au moins une feuille de match, contiguës depuis i = 1.
  select player_id, match_id, count(*) filter (where wk = rn)::integer as weeks_without_rest
  from (
    select *, row_number() over (partition by player_id, match_id order by wk) as rn
    from (select distinct player_id, match_id, (d - h_date - 1) // 7 + 1 as wk from pairs)
  )
  group by player_id, match_id
)
select
  b.player_id,
  b.match_id,
  {% for k in [7, 14, 28, 56, 365] -%}
  coalesce(a.min_{{ k }}d, 0) as min_{{ k }}d,
  {% endfor -%}
  coalesce(a.min_intl_56d, 0) as min_intl_56d,
  coalesce(a.min_club_28d, 0) as min_club_28d,
  coalesce(a.apps_20min_365d, 0) as apps_20min_365d,
  coalesce(a.fge_30d, 0.0) as fge_30d,
  coalesce(a.ewma_acute, 0.0) as ewma_acute,
  coalesce(a.ewma_chronic, 0.0) as ewma_chronic,
  coalesce(a.season_minutes, 0) as season_minutes,
  coalesce(b.match_date - a.last_played, 999)::integer as days_since_last_match,
  a.last_played is null as days_since_last_match_missing,
  coalesce(b.match_date - a.last_played < 5, false) as short_turnaround,
  coalesce(a.n_short_turnarounds_28d, 0) as n_short_turnarounds_28d,
  coalesce(w.weeks_without_rest, 0) as weeks_without_rest,
  coalesce(b.match_date - a.last_test, 999)::integer as days_since_last_test,
  coalesce(a.intl_caps_365d, 0) as intl_caps_365d
from {{ ref('int_ml_base') }} b
left join agg a using (player_id, match_id)
left join weeks w using (player_id, match_id)
