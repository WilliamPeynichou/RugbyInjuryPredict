-- F17 : table d'apprentissage, une ligne par joueur éligible × match (docs/04 §4).
-- Pseudonymisée (player_key seul). Colonnes : rugby_risk.features.registry (partition testée).
-- dataset_version = md5 du contenu trié : deux builds identiques -> même version.
with rows as (
  select
    d.player_key,
    b.match_id,
    b.season_id,
    b.kickoff_ts,
    b.kickoff_ts - interval 1 second as as_of_ts,
    b.on_sheet,
    b.played,
    b.is_starter,
    b.minutes_played,
    t.y_injury,
    t.y_injury_any_7d,
    t.y_days_missed,
    t.y_injury_conf,
    l.* exclude (player_id, match_id),
    s.* exclude (player_id, match_id),
    h.* exclude (player_id, match_id),
    p.* exclude (player_id, match_id),
    c.* exclude (player_id, match_id)
  from {{ ref('int_ml_base') }} b
  join {{ ref('dim_player') }} d using (player_id)
  join {{ ref('int_ml_targets') }} t using (player_id, match_id)
  join {{ ref('int_ml_feat_load') }} l using (player_id, match_id)
  join {{ ref('int_ml_feat_sequence') }} s using (player_id, match_id)
  join {{ ref('int_ml_feat_injury_history') }} h using (player_id, match_id)
  join {{ ref('int_ml_feat_player') }} p using (player_id, match_id)
  join {{ ref('int_ml_feat_context') }} c using (player_id, match_id)
),
-- Les features flottantes (EWMA, ratios) sont exclues : leur sommation SQL n'est pas
-- ordonnée et varie d'1 ulp d'un build à l'autre. La version identifie le JEU DE DONNÉES
-- (grain + événements), pas le bruit numérique. Liste tenue en phase avec registry.py.
{% set float_cols = ['fge_30d', 'ewma_acute', 'ewma_chronic', 'age', 'bmi_rel_position',
                     'opponent_strength'] %}
version as (
  select md5(coalesce(string_agg(r::varchar, '|' order by r.player_key, r.match_id), ''))
    as dataset_version
  from (select * exclude ({{ float_cols | join(', ') }}) from rows) r
)
select rows.*, version.dataset_version from rows cross join version
