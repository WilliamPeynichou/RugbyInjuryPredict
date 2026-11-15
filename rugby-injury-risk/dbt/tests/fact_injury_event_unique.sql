-- F16 : unicité du grain docs/04 §3 (player_id, onset_date, body_region).
select player_id, onset_date, body_region, count(*) as n
from {{ ref('fact_injury_event') }}
group by 1, 2, 3
having count(*) > 1
