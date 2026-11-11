-- F25 — Tables publiques agrégées (docs/04-data-model.md §5, docs/07-legal-rgpd.md §2).
-- Aucune colonne nominative : ni player_key, ni player_id, ni nom, ni date de naissance.
-- Écriture : uniquement la clé service (job batch F25), toujours derrière serving/guard.py.
-- Lecture : anonyme (rôle anon), via RLS. Aucune écriture publique.

create table if not exists public.pred_position_curve (
    model_version      text        not null,
    season_id          text        not null,
    position_code      text        not null,
    n_consecutive      integer     not null check (n_consecutive between 0 and 15),
    scenario           text        not null,
    p_mean             double precision not null check (p_mean between 0 and 1),
    p_low90            double precision not null check (p_low90 between 0 and 1),
    p_high90           double precision not null check (p_high90 between 0 and 1),
    cum_mean           double precision not null check (cum_mean between 0 and 1),
    cum_low90          double precision not null check (cum_low90 between 0 and 1),
    cum_high90         double precision not null check (cum_high90 between 0 and 1),
    n_players_support  integer     not null check (n_players_support >= 10),
    computed_at        timestamptz not null,
    primary key (model_version, season_id, position_code, scenario, n_consecutive)
);

create table if not exists public.pred_position_season (
    model_version          text        not null,
    season_id              text        not null,
    position_code          text        not null,
    position_group         text        not null,
    incidence_per_1000h    double precision not null,
    incidence_low90        double precision not null,
    incidence_high90       double precision not null,
    injuries_count_bucket  text        not null check (injuries_count_bucket in ('<10', '10-24', '25-49', '50+')),
    exposure_hours         double precision not null,
    n_matches_played       integer     not null,
    n_players_support      integer     not null check (n_players_support >= 10),
    computed_at            timestamptz not null,
    primary key (model_version, season_id, position_code)
);

create table if not exists public.calibration_public (
    model_version      text    not null,
    test_season        text    not null,
    position_group     text    not null,
    bin                integer not null,
    p_pred_mean        double precision not null,
    p_obs              double precision not null,
    n                  integer not null,
    n_players_support  integer not null check (n_players_support >= 10),
    primary key (model_version, test_season, position_group, bin)
);

create table if not exists public.model_registry_public (
    model_version    text    primary key,
    model_name       text    not null,
    role             text    not null,
    promoted         boolean not null default false,
    trained_at       timestamptz not null,
    train_seasons    text    not null,
    test_season      text    not null,
    dataset_version  text    not null,
    n_test           integer not null,
    brier            double precision,
    brier_low90      double precision,
    brier_high90     double precision,
    brier_skill      double precision,
    logloss          double precision,
    auc_roc          double precision,
    calib_slope      double precision,
    calib_intercept  double precision,
    notes            text
);

-- RLS : lecture anonyme seule, aucune politique d'écriture (la clé service contourne RLS).
alter table public.pred_position_curve   enable row level security;
alter table public.pred_position_season  enable row level security;
alter table public.calibration_public    enable row level security;
alter table public.model_registry_public enable row level security;

create policy "lecture publique" on public.pred_position_curve   for select to anon using (true);
create policy "lecture publique" on public.pred_position_season  for select to anon using (true);
create policy "lecture publique" on public.calibration_public    for select to anon using (true);
create policy "lecture publique" on public.model_registry_public for select to anon using (true);

revoke insert, update, delete on public.pred_position_curve   from anon, authenticated;
revoke insert, update, delete on public.pred_position_season  from anon, authenticated;
revoke insert, update, delete on public.calibration_public    from anon, authenticated;
revoke insert, update, delete on public.model_registry_public from anon, authenticated;
