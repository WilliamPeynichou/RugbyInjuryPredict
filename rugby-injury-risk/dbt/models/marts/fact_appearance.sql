-- Joueur × match sur la feuille. Poste joué : source > maillot 1-15 > poste principal.
-- minutes_played NULL quand aucune source ne donne les minutes (LNR, ESPN, World Rugby seuls).
select
  r.match_id,
  r.player_id,
  t.team_id,
  r.shirt_number::integer as shirt_number,
  r.is_starter,
  coalesce(r.position_source, s.position_code, d.primary_position) as position_played,
  r.minutes_played::integer as minutes_played,
  case when r.is_starter then 0 when r.minutes_played > 0 then greatest(80 - r.minutes_played, 0) end
    as minute_on,
  -- shortcut: minute_off seulement pour un titulaire sorti avant 80' ; remplaçant expulsé non daté.
  case when r.is_starter and r.minutes_played < 80 then r.minutes_played end as minute_off,
  case when r.red_cards > 0 then 'card' else 'unknown' end as off_reason,
  coalesce(r.yellow_cards, 0)::integer as yellow_cards,
  coalesce(r.red_cards, 0)::integer as red_cards,
  r.primary_source
from {{ ref('int_appearance__reconciled') }} r
join {{ ref('dim_team') }} t on t.name = r.team_name
left join {{ ref('ref_positions') }} s
  on r.shirt_number between 1 and 15
  and list_contains(string_split(s.shirt_numbers, ';'), r.shirt_number::varchar)
left join {{ ref('dim_player') }} d on d.player_id = r.player_id
