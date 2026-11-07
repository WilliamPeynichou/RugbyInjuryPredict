-- F17 docs/05 §3, §5 : individu, protection. Gabarit manquant imputé par la médiane du poste
-- (repli : médiane globale) + flag. Poste = poste principal (dim_player), connu avant le match.
with p as (
  select
    player_id, birth_date, full_name, height_cm, weight_kg,
    coalesce(primary_position, 'UNKNOWN') as position_code, position_group, unit,
    weight_kg / pow(height_cm / 100, 2) as bmi
  from {{ ref('dim_player') }}
),
med as (
  select position_code, median(height_cm) as h, median(weight_kg) as w, median(bmi) as bmi
  from p group by position_code
),
gmed as (select median(height_cm) as h, median(weight_kg) as w, median(bmi) as bmi from p),
dims as (
  select
    p.*,
    coalesce(p.height_cm, med.h, gmed.h)::double as height_imp,
    coalesce(p.weight_kg, med.w, gmed.w)::double as weight_imp,
    coalesce(med.bmi, gmed.bmi) as bmi_med
  from p left join med using (position_code) cross join gmed
),
seasons as (
  select player_id, season_id, bool_or(played) as any_played
  from {{ ref('int_ml_base') }} group by player_id, season_id
),
pro as (
  select
    player_id, season_id,
    coalesce(sum(any_played::integer) over (
      partition by player_id order by season_id
      rows between unbounded preceding and 1 preceding
    ), 0)::integer as pro_seasons
  from seasons
),
regimes as (
  select b.player_id, b.match_id, arg_max(r.regime, r.start_date) as regime
  from {{ ref('int_ml_base') }} b
  join {{ ref('ref_rules_protection') }} r
    on b.match_date between r.start_date and coalesce(r.end_date, date '9999-12-31')
  group by b.player_id, b.match_id
)
select
  b.player_id,
  b.match_id,
  d.position_code,
  d.position_group,
  d.unit,
  (b.match_date - d.birth_date) / 365.25 as age,
  d.birth_date is null as age_missing,
  d.height_imp as height_cm,
  d.height_cm is null as height_missing,
  d.weight_imp as weight_kg,
  d.weight_kg is null as weight_missing,
  d.weight_imp / pow(d.height_imp / 100, 2) - d.bmi_med as bmi_rel_position,
  pro.pro_seasons,
  exists (
    select 1 from {{ ref('ref_protected_players') }} pp
    where pp.season_id = b.season_id and pp.player_name = d.full_name
  ) as protected_list,
  coalesce(r.regime, 'none') as protection_regime,
  exists (
    select 1 from {{ ref('ref_test_windows') }} tw
    where b.match_date between tw.start_date and tw.end_date
  ) as intl_window
from {{ ref('int_ml_base') }} b
join dims d using (player_id)
join pro using (player_id, season_id)
left join regimes r using (player_id, match_id)
