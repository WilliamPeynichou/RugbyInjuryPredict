-- quality_flag = 'low' si moins de 98 % des matchs Top 14 de la saison passent le contrôle des minutes.
with q as (
  select season_id, avg(minutes_ok::integer) as pct_minutes_ok
  from {{ ref('match_minutes_check') }}
  where competition_code = 'TOP14'
  group by season_id
)
select
  s.*,
  q.pct_minutes_ok,
  case when q.season_id is null then null when q.pct_minutes_ok < 0.98 then 'low' else 'ok' end
    as quality_flag
from {{ ref('ref_seasons') }} s left join q using (season_id)
