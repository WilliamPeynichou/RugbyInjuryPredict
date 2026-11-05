-- Signal « sortie précoce » (F12) : une ligne par apparition candidate, signal_strength ∈ [0, 1].
-- Seuils : config/injury_rules.yaml (var `exit_signal`, passée par rugby_risk.injuries.rules).
{%- set r = var('exit_signal') %}
with app as (
  select
    a.match_id, a.player_id, a.team_id, a.is_starter, a.minute_off, a.off_reason,
    p.position_group
  from {{ ref('fact_appearance') }} a
  left join {{ ref('ref_positions') }} p on p.position_code = a.position_played
),
exits as (
  -- un carton n'est pas une sortie médicale ; minute_off NULL = a fini le match
  select
    *,
    count(*) over (partition by match_id, team_id, position_group, minute_off) > 1
      as block_change
  from app
  where minute_off is not null and off_reason <> 'card'
),
base as (
  select
    *,
    case
      when not is_starter then {{ r.sub_off_strength }}
      when minute_off <= {{ r.very_early_minute }} then {{ r.very_early_strength }}
      when minute_off < case position_group
        {%- for group, minute in r.early_exit_minute.items() %} when '{{ group }}' then {{ minute }}
        {%- endfor %} end then {{ r.early_exit_strength }}
      else 0
    end as base_strength
  from exits
),
-- ATTENTION : information POSTÉRIEURE au match (présence au match suivant de l'équipe).
-- Autorisée pour la labellisation (cible), INTERDITE pour les features (docs/05, as_of_ts).
next_match as (
  select
    e.match_id, e.player_id,
    lead(e.on_sheet) over (partition by e.player_id, e.team_id order by m.kickoff_ts)
      as next_on_sheet
  from {{ ref('fact_eligibility') }} e
  join {{ ref('fact_match') }} m using (match_id)
),
scored as (
  select
    b.*,
    coalesce(not n.next_on_sheet, false) as absent_next,
    least(
      1.0,
      b.base_strength * case when b.block_change then {{ r.block_change_factor }} else 1 end
      + case when not n.next_on_sheet then {{ r.absent_next_bonus }} else 0 end
    ) as signal_strength
  from base b
  left join next_match n using (match_id, player_id)
  where b.base_strength > 0
)
select
  match_id, player_id, team_id, is_starter, position_group, minute_off, block_change,
  absent_next, signal_strength,
  -- colonne dérivée : fact_appearance.off_reason (sources) n'est jamais écrasé
  case when signal_strength >= {{ r.suspected_threshold }} then 'injury_suspected'
    else off_reason end as off_reason_derived
from scored
