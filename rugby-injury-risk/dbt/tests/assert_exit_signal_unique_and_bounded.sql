-- Une ligne par apparition, force dans [0, 1].
select match_id, player_id from {{ ref('int_injury_signal__exit') }}
group by match_id, player_id
having count(*) > 1 or bool_or(signal_strength not between 0 and 1)
