-- F17 docs/05 §4 : antécédents, épisodes de confiance >= seuil avec onset_date < D.
-- Jours manqués : jusqu'au retour s'il précède D, sinon jusqu'à D (aucune date future utilisée).
with inj as (
  select player_id, onset_date, return_date, coalesce(is_concussion, false) as is_concussion
  from {{ ref('fact_injury_event') }}
  where source_confidence >= {{ var('injury_conf_threshold', 0.6) }}
),
agg as (
  select
    b.player_id,
    b.match_id,
    count(i.onset_date) filter (where i.onset_date >= b.match_date - 365)::integer as n_365,
    count(i.onset_date)::integer as n_career,
    sum(least(coalesce(i.return_date, b.match_date), b.match_date) - i.onset_date)
      filter (where i.onset_date >= b.match_date - 365)::integer as missed_365,
    max(i.onset_date) as last_onset,
    max(i.return_date) filter (where i.return_date < b.match_date) as last_return,
    count(*) filter (where i.is_concussion and i.onset_date >= b.match_date - 365)::integer
      as concussions_365
  from {{ ref('int_ml_base') }} b
  join inj i on i.player_id = b.player_id and i.onset_date < b.match_date
  group by b.player_id, b.match_id
)
select
  b.player_id,
  b.match_id,
  coalesce(a.n_365, 0) as n_prior_injuries_365d,
  coalesce(a.n_career, 0) as n_prior_injuries_career,
  coalesce(a.missed_365, 0) as days_missed_365d,
  coalesce(b.match_date - a.last_onset, 999)::integer as days_since_last_injury,
  coalesce(b.match_date - a.last_return, 999)::integer as days_since_return,
  coalesce(b.match_date - a.last_return, 999) <= 56 as recent_return_8w,
  coalesce(a.concussions_365, 0) as prior_concussions_365d,
  (b.match_date - b.first_seen)::integer as observed_history_days
from {{ ref('int_ml_base') }} b
left join agg a using (player_id, match_id)
