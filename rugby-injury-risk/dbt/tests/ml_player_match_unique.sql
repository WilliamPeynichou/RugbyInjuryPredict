-- Grain de ml_player_match : (player_key, match_id) unique.
select player_key, match_id from {{ ref('ml_player_match') }}
group by player_key, match_id having count(*) > 1
