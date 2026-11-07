-- F17 docs/05 §2 : matchs d'équipe consécutifs (club + sélection) avant t, par saison.
-- Valeur de la ligne t = longueur de la série en cours au match d'équipe précédent.
with runs as (
  select
    *,
    {{ consecutive_run_id('player_id, season_id', 'kickoff_ts, match_id', 'played') }} as r_play,
    {{ consecutive_run_id('player_id, season_id', 'kickoff_ts, match_id', 'is_starter') }}
      as r_start,
    {{ consecutive_run_id('player_id, season_id', 'kickoff_ts, match_id', 'minutes >= 60') }}
      as r_heavy
  from {{ ref('int_ml_base') }}
),
streaks as (
  select
    *,
    {% for cond, run in [('played', 'r_play'), ('is_starter', 'r_start'),
                         ('minutes >= 60', 'r_heavy')] -%}
    sum(({{ cond }})::integer) over (
      partition by player_id, season_id, {{ run }} order by kickoff_ts, match_id
      rows between unbounded preceding and current row
    ) as s_{{ run }}{{ "," if not loop.last }}
    {% endfor %}
  from runs
)
select
  player_id,
  match_id,
  coalesce(lag(s_r_play) over w, 0)::integer as consecutive_matches,
  coalesce(lag(s_r_start) over w, 0)::integer as consecutive_starts,
  coalesce(lag(s_r_heavy) over w, 0)::integer as consecutive_heavy
from streaks
window w as (partition by player_id, season_id order by kickoff_ts, match_id)
