-- Signal « absence » (F13) : une ligne par séquence consécutive de matchs d'équipe sans
-- on_sheet, classée par règles ordonnées (première vraie gagne). Seuils : var `absence_signal`
-- (config/injury_rules.yaml). « International » = feuille nationale dans la même fenêtre de
-- tests, ou fenêtre atteinte et ≥ 1 sélection dans les 12 derniers mois.
{%- set a = var('absence_signal') %}
with in_sheet as (
  select
    e.match_id, e.player_id, e.team_id, m.season_id, m.kickoff_ts,
    {{ utc_date('m.kickoff_ts') }} as match_date
  from {{ ref('fact_eligibility') }} e
  join {{ ref('fact_match') }} m using (match_id)
  join {{ ref('dim_team') }} t on t.team_id = e.team_id
  where e.on_sheet
),
runs as (
  select
    *,
    sum(case when on_sheet then 1 else 0 end) over (
      partition by player_id, season_id order by kickoff_ts
      rows between unbounded preceding and current row
    ) as seq_id,
    -- dernier match sur la feuille strictement avant (rouge / signal de sortie F12 s'y lisent)
    max(case when on_sheet then match_id end) over (
      partition by player_id, season_id order by kickoff_ts
      rows between unbounded preceding and 1 preceding
    ) as prev_played_match_id,
    lead(on_sheet) over (partition by player_id, season_id order by kickoff_ts) as next_on_sheet,
    lead(kickoff_ts) over (partition by player_id, season_id order by kickoff_ts)
      is not null as has_next
  from (
    select
      m.match_id, e.player_id, e.team_id, m.season_id, m.kickoff_ts, m.competition_code,
      e.on_sheet
    from {{ ref('fact_eligibility') }} e
    join {{ ref('fact_match') }} m using (match_id)
  )
),
spans as (
  select
    player_id, season_id, seq_id,
    min(kickoff_ts) as start_ts, max(kickoff_ts) as end_ts,
    count(*) as n_matches,
    arg_max(match_id, kickoff_ts) as last_match_id,
    arg_max(has_next, kickoff_ts) as has_next,
    arg_max(prev_played_match_id, kickoff_ts) as prev_played_match_id,
    min({{ utc_date('kickoff_ts') }}) as start_date,
    max({{ utc_date('kickoff_ts') }}) as end_date
  from runs
  where not on_sheet
  group by player_id, season_id, seq_id
),
context as (
  select
    s.*,
    -- position pour le rapport (poste principal, sinon poste joué)
    coalesce(d.primary_position, m.position_played) as position_code,
    m.minute_off, m.red_cards,
    -- joueur sur une feuille nationale pendant la fenêtre de la période ?
    exists(
      select 1 from in_sheet i
      join {{ ref('dim_team') }} t on t.team_id = i.team_id and t.is_national
      where i.player_id = s.player_id
        and i.match_date between s.start_date and s.end_date
    ) as intl_sheet_in_window,
    -- ≥ 1 sélection dans les 12 derniers mois avant le début de l'absence ?
    exists(
      select 1 from in_sheet i
      join {{ ref('dim_team') }} t on t.team_id = i.team_id and t.is_national
      where i.player_id = s.player_id
        and i.match_date between s.start_date - {{ a.intl_history_days }} and s.start_date
    ) as intl_sheet_history,
    -- fenêtre de tests chevauchant la période ?
    exists(
      select 1 from {{ ref('ref_test_windows') }} w
      where greatest(w.start_date, s.start_date) <= least(w.end_date, s.end_date)
    ) as in_test_window,
    exists(
      select 1 from {{ ref('ref_protected_players') }} p
      where p.season_id = s.season_id
        and lower(replace(replace(p.player_name::varchar, ' ', ''), '-', '')) =
            lower(replace(replace(coalesce(d.full_name, ''::varchar), ' ', ''), '-', ''))
    ) as is_protected,
    -- sortie F12 (signal de sortie) au dernier match joué avant l'absence
    (select max(x.signal_strength) from {{ ref('int_injury_signal__exit') }} x
     where x.player_id = s.player_id and x.match_id = s.prev_played_match_id) >=
      {{ a.exit_link_threshold }} as has_exit_signal
  from spans s
  left join {{ ref('fact_appearance') }} m on m.match_id = s.prev_played_match_id
    and m.player_id = s.player_id
  left join {{ ref('dim_player') }} d on d.player_id = s.player_id
)
select
  *,
  case
    when intl_sheet_in_window or (in_test_window and intl_sheet_history) then 'international_duty'
    when coalesce(red_cards, 0) > 0
      and n_matches <= {{ a.suspension_max_matches }} then 'suspension'
    when is_protected and n_matches <= {{ a.protected_rest_max_matches }} then 'protected_rest'
    when n_matches >= {{ a.min_matches_injury_candidate }} or has_exit_signal
      then 'injury_candidate'
    when n_matches = 1 then 'rotation'
    else 'unknown'
  end as absence_reason,
  has_next is not true as censored_end_of_season
from context
