-- Fusion des feuilles de match multi-sources : une ligne par (match_id, player_id).
-- Composition/poste : priorité LNR > allrugby > World Rugby > ESPN ; minutes : première source non nulle.
with app as (
  select
    m.match_id, x.player_id, a.source, a.shirt_number, a.is_starter, a.minutes_played,
    a.yellow_cards, a.red_cards, p.position_code as position_source,
    {{ canonical_team('a.team_name', 'a.source') }} as team_name,
    {{ source_priority('a.source') }} as priority
  from {{ ref('stg_appearance') }} a
  join {{ ref('int_match__reconciled') }} m
    on m.source = a.source and m.source_match_id = a.source_match_id
  join {{ ref('stg_player_source_xref') }} x
    on x.source = a.source and x.source_player_id = a.source_player_id
  left join {{ ref('ref_positions') }} p on p.position_code = a.position_raw
)
select
  match_id,
  player_id,
  arg_min(team_name, priority) as team_name,
  arg_min(shirt_number, priority) filter (where shirt_number is not null) as shirt_number,
  arg_min(is_starter, priority) as is_starter,
  arg_min(position_source, priority) filter (where position_source is not null) as position_source,
  arg_min(minutes_played, priority) filter (where minutes_played is not null) as minutes_played,
  max(yellow_cards) as yellow_cards,
  max(red_cards) as red_cards,
  arg_min(source, priority) as primary_source
from app
group by match_id, player_id
