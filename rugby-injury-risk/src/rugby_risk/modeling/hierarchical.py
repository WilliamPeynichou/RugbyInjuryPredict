"""M2 hierarchical Bayesian discrete-time hazard (F22, docs/06 §2): the production model.

    cloglog(h_i) = alpha + a_unit[u] + a_group[g] + a_code[c]       (non-centred, partial pooling)
                 + b_cons[g] * consecutive_matches_std               (slope per group, pooled)
                 + b_load * min_28d_std + X_i beta                   (fixed effects, B-splines)
                 + u_player[p] + v_team_season[t] + log(minutes/80)

Priors come from `modeling/priors.py` only (docs/06 §2). `min_28d` enters linearly: the only
informed load prior (Williams 2017, log(1,14) per +3,2 FGE / 30 days) is a linear slope, which
a spline basis cannot carry (journal F22). Every transformation (imputation, winsorisation,
standardisation, spline knots, category levels, player / team-season indices) is learned on the
training fold only via `design.build_design` (no leakage).

IPW (F21): stabilized truncated weights enter a weighted Bernoulli log-likelihood through
`pm.Potential` (pseudo-posterior). Out-of-sample players and team-seasons are never set to 0:
their random effect is integrated over the population law N(0, sigma^2) of each posterior draw
by Gauss-Hermite quadrature, so a new player's prediction carries the population variance.
Test seasons are always new team-seasons.
"""

from __future__ import annotations

import math
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import numpy as np
import polars as pl

from rugby_risk.features.registry import FEATURES
from rugby_risk.modeling import priors
from rugby_risk.modeling.curves import (
    SCENARIOS_PATH,
    Scenarios,
    cumulative_risk,
    hazard_curve_draws,
    load_scenarios,
    scenario_profiles,
)
from rugby_risk.modeling.design import (
    EXPOSURE_REF_MINUTES,
    DesignSpec,
    FittedTransform,
    build_design,
)
from rugby_risk.modeling.selection import SelectionSpec, WeightDiagnostics, fit_ipw_weights

SLOPE_TERM: Final = "consecutive_matches"
LOAD_TERM: Final = "min_28d"
FIXED_SPEC: Final = DesignSpec(
    categorical=("surface", "season_period"),
    splines=(
        ("apps_20min_365d", 3),
        ("days_since_last_match_capped", 3),
        ("age", 3),
    ),
    linear=(
        SLOPE_TERM,
        LOAD_TERM,
        "short_turnaround",
        "intl_window",
        "recent_return_8w",
        "n_prior_injuries_365d",
        "prior_concussions_365d",
        "is_playoff",
    ),
    interactions=(),
)
# Variante « historique de blessure » (exploration, F22 journal) : même modèle, priors et
# sampler ; seul le design fixe gagne deux termes dérivés de days_since_last_injury.
# La sentinelle 999 (« jamais blessé ») n'est jamais lue comme une durée : elle est portée par
# `ever_injured`, et log1p_days_since_injury vaut 0 pour ces lignes.
INJHIST_SPEC: Final = DesignSpec(
    categorical=FIXED_SPEC.categorical,
    splines=FIXED_SPEC.splines,
    linear=(*FIXED_SPEC.linear, "ever_injured", "log1p_days_since_injury"),
    interactions=FIXED_SPEC.interactions,
)
POSITION_LEVELS: Final = ("unit", "position_group", "position_code")
R_HAT_MAX: Final = 1.01
ESS_MIN: Final = 400.0
CI_LEVEL: Final = 0.90
CUMULATIVE_HORIZON: Final = 5
MINUTES_PER_HOUR: Final = 60.0
PER_1000H: Final = 1000.0
_GH_NODES: Final = 20
_TABLE_NS: Final = (0, 3, 6, 9, 12, 15)
_SEP: Final = "|"


@dataclass(frozen=True)
class SamplerConfig:
    """NUTS settings. `player_fraction` < 1 subsamples players (stratified by group): --fast."""

    draws: int = 1000
    tune: int = 1000
    chains: int = 4
    cores: int = 4
    target_accept: float = 0.99  # hiérarchie non centrée : 0.9 laisse des divergences (journal F22)
    player_fraction: float = 1.0
    max_prediction_draws: int = 400
    prior_draws: int = 500

    @property
    def fast(self) -> bool:
        return self.player_fraction < 1.0


FAST_SAMPLER: Final = SamplerConfig(draws=500, tune=500, chains=2, cores=2, player_fraction=0.5)


@dataclass(frozen=True)
class McmcDiagnostics:
    """Convergence of one fit (docs/06 §6): R-hat <= 1.01, ESS bulk/tail >= 400, 0 divergence."""

    r_hat_max: float
    ess_bulk_min: float
    ess_tail_min: float
    divergences: int
    seconds: float

    @property
    def ok(self) -> bool:
        return (
            self.r_hat_max <= R_HAT_MAX
            and self.ess_bulk_min >= ESS_MIN
            and self.ess_tail_min >= ESS_MIN
            and self.divergences == 0
        )


@dataclass(frozen=True)
class _Index:
    """Hierarchy and random-effect levels learned on the training fold."""

    codes: tuple[str, ...]
    groups: tuple[str, ...]
    units: tuple[str, ...]
    group_of_code: np.ndarray
    unit_of_group: np.ndarray
    players: dict[str, int]
    teams: dict[str, int]


@dataclass(frozen=True)
class _Data:
    code: np.ndarray
    group: np.ndarray
    player: np.ndarray  # -1 = unknown player (integrated)
    team: np.ndarray  # -1 = unknown team-season (integrated)
    x_cons: np.ndarray
    x_load: np.ndarray
    X: np.ndarray
    offset: np.ndarray
    y: np.ndarray | None
    minutes: np.ndarray


@dataclass
class _Posterior:
    draws: dict[str, np.ndarray] = field(default_factory=dict)


def _team_season(df: pl.DataFrame) -> list[str] | None:
    if "team_id" not in df.columns or "season_id" not in df.columns:
        return None
    teams = df.get_column("team_id").cast(pl.String).fill_null("unknown").to_list()
    seasons = df.get_column("season_id").cast(pl.String).to_list()
    return [f"{t}{_SEP}{s}" for t, s in zip(teams, seasons, strict=True)]


def _learn_index(train: pl.DataFrame) -> _Index:
    rows = train.select([pl.col(c).cast(pl.String) for c in POSITION_LEVELS]).unique()
    if rows.select(pl.col("position_code").is_duplicated().any()).item():
        raise ValueError("position_code rattaché à plusieurs position_group/unit au train")
    if (
        rows.select(pl.col("position_group").n_unique()).item()
        != rows.select(["position_group", "unit"]).unique().height
    ):
        raise ValueError("position_group rattaché à plusieurs unit au train")
    codes = tuple(sorted(rows["position_code"].to_list()))
    groups = tuple(sorted(set(rows["position_group"].to_list())))
    units = tuple(sorted(set(rows["unit"].to_list())))
    code_group = dict(zip(rows["position_code"], rows["position_group"], strict=True))
    group_unit = dict(zip(rows["position_group"], rows["unit"], strict=True))
    players = sorted(set(train.get_column("player_key").cast(pl.String).to_list()))
    teams = sorted(set(_team_season(train) or []))
    if not teams:
        raise ValueError("team_id/season_id absents du train : effet équipe-saison impossible")
    return _Index(
        codes=codes,
        groups=groups,
        units=units,
        group_of_code=np.array([groups.index(code_group[c]) for c in codes]),
        unit_of_group=np.array([units.index(group_unit[g]) for g in groups]),
        players={p: i for i, p in enumerate(players)},
        teams={t: i for i, t in enumerate(teams)},
    )


def _split_design(columns: tuple[str, ...]) -> tuple[int, int | None, list[int]]:
    cols = list(columns)
    if SLOPE_TERM not in cols:
        raise ValueError(f"{SLOPE_TERM} écarté du design (constant au train) : M2 impossible")
    load = cols.index(LOAD_TERM) if LOAD_TERM in cols else None
    keep = [j for j, c in enumerate(cols) if c not in ("Intercept", SLOPE_TERM, LOAD_TERM)]
    return cols.index(SLOPE_TERM), load, keep


def _scenario_draws(model: HierarchicalHazardModel, code: str, scenario: str) -> float:
    """Risque cumulé médian (horizon CUMULATIVE_HORIZON) d'un scénario de charge par poste."""
    draws = hazard_curve_draws(model, code, scenario=scenario).mean(axis=0)
    return cumulative_risk(draws[:CUMULATIVE_HORIZON])


def _marginal_hazard(draws: dict[str, np.ndarray], data: _Data) -> np.ndarray:
    """P(injury) per (draw, row), random effects of unknown levels integrated (Gauss-Hermite)."""
    eta = (
        draws["alpha"][:, None]
        + draws["position_effect"][:, data.code]
        + draws["slope"][:, data.group] * data.x_cons
        + draws["beta_load"][:, None] * data.x_load
        + draws["beta"] @ data.X.T
        + data.offset
    )
    var = np.zeros_like(eta)
    for key, sigma, idx in (
        ("player_effect", "sigma_player", data.player),
        ("team_effect", "sigma_team", data.team),
    ):
        known = idx >= 0
        eta[:, known] += draws[key][:, idx[known]]
        var[:, ~known] += draws[sigma][:, None] ** 2
    scale = np.sqrt(2.0 * var)
    nodes, weights = np.polynomial.hermite.hermgauss(_GH_NODES)
    p = np.zeros_like(eta)
    for x, w in zip(nodes, weights, strict=True):
        p += w * -np.expm1(-np.exp(eta + scale * x))
    return np.asarray(p / math.sqrt(math.pi), dtype=float)


def _stack(group: Any, names: tuple[str, ...], limit: int, seed: int) -> dict[str, np.ndarray]:
    """xarray posterior/prior group -> {name: (draws, ...)} with at most `limit` draws."""
    out = {}
    for name in names:
        values = np.asarray(group[name].values, dtype=float)
        out[name] = values.reshape(-1, *values.shape[2:])
    total = len(out[names[0]])
    if total > limit:
        pick = np.sort(np.random.default_rng(seed).choice(total, size=limit, replace=False))
        out = {k: v[pick] for k, v in out.items()}
    return out


_DRAW_NAMES: Final = (
    "alpha",
    "position_effect",
    "slope",
    "beta_load",
    "beta",
    "sigma_player",
    "player_effect",
    "sigma_team",
    "team_effect",
)


class HierarchicalHazardModel:
    """M2 (F22): PyMC hierarchical cloglog hazard, implements `RiskModel` (F18)."""

    def __init__(  # noqa: PLR0913 - pipeline M2 : sampler, IPW, scénarios
        self,
        *,
        sampler: SamplerConfig | None = None,
        ipw: bool = True,
        truncate: tuple[float, float] = (0.01, 0.99),
        seed: int = 0,
        scenarios_path: Path = SCENARIOS_PATH,
        name: str | None = None,
        spec: DesignSpec = FIXED_SPEC,
        registry_name: str = "rugby-risk-m2",
    ) -> None:
        self.sampler = sampler or SamplerConfig()
        self.ipw = ipw
        self.truncate = truncate
        self.seed = seed
        self.spec = spec
        self.name = name or "m2_hierarchical"
        self.requires_eligible = ipw
        self.registry_name = registry_name
        self.scenarios_: Scenarios = load_scenarios(scenarios_path)
        self.profiles_: dict[str, dict[str, Any]] = {}
        self.transform_: FittedTransform | None = None
        self.index_: _Index | None = None
        self.fixed_terms_: tuple[str, ...] = ()
        self.load_prior_: tuple[float, float] = (0.0, 0.0)
        self.idata_: Any = None
        self.posterior_: _Posterior | None = None
        self.diagnostics_: McmcDiagnostics | None = None
        self.ipw_diagnostics_: WeightDiagnostics | None = None
        self.warning_: str | None = None
        self.prior_incidence_: pl.DataFrame | None = None
        self.n_train_rows_: int = 0
        self._check_scenarios()

    def _check_scenarios(self) -> None:
        unknown = {
            name: sorted(set(o) - set(FEATURES)) for name, o in self.scenarios_.overrides.items()
        }
        bad = {k: v for k, v in unknown.items() if v}
        if bad:
            raise ValueError(f"Scénarios hors registre : {bad}")

    @property
    def status(self) -> str:
        """`failed` when MCMC diagnostics miss docs/06 §6 (the run is then not promotable)."""
        if self.diagnostics_ is None:
            return "not_fitted"
        return "ok" if self.diagnostics_.ok else "failed"

    # --- données -----------------------------------------------------------------------

    def _data(self, df: pl.DataFrame) -> _Data:
        index = self.index_
        if index is None:
            raise RuntimeError("fit() doit être appelé avant la prédiction")
        design = build_design(df, self.spec, self.transform_)
        i_cons, i_load, keep = _split_design(design.columns)
        codes = df.get_column("position_code").cast(pl.String).to_list()
        unknown = sorted(set(codes) - set(index.codes))
        if unknown:
            raise ValueError(f"Postes absents du train : {unknown}")
        code = np.array([index.codes.index(c) for c in codes], dtype=int)
        keys = (
            df.get_column("player_key").cast(pl.String).to_list()
            if "player_key" in df.columns
            else [None] * len(df)
        )
        known_teams = _team_season(df)
        team_idx = (
            [index.teams.get(t, -1) for t in known_teams]
            if known_teams is not None
            else [-1] * len(df)
        )
        minutes = df.get_column(self.spec.exposure).cast(pl.Float64).to_numpy()
        return _Data(
            code=code,
            group=index.group_of_code[code],
            player=np.array([index.players.get(k, -1) if k else -1 for k in keys], dtype=int),
            team=np.array(team_idx, dtype=int),
            x_cons=design.X[:, i_cons],
            x_load=design.X[:, i_load] if i_load is not None else np.zeros(len(df)),
            X=design.X[:, keep],
            offset=design.offset,
            y=design.y,
            minutes=minutes,
        )

    def _prepare(self, train: pl.DataFrame) -> _Data:
        """Learn every transform on the training fold, then encode it."""
        design = build_design(train, self.spec)
        if design.y is None:
            raise ValueError(f"Cible absente du train : {self.spec.target}")
        self.transform_ = design.transform
        self.index_ = _learn_index(train)
        _, i_load, keep = _split_design(design.columns)
        self.fixed_terms_ = tuple(design.columns[j] for j in keep)
        std = design.transform.stds.get(LOAD_TERM, 0.0) if i_load is not None else 0.0
        self.load_prior_ = priors.m2_load_prior(std) if std > 0 else (0.0, priors.M2_LOAD_SD)
        return self._data(train)

    def _subsample(self, train: pl.DataFrame) -> np.ndarray:
        """Row mask of a player-level subsample stratified by position_group (--fast)."""
        if not self.sampler.fast:
            return np.ones(len(train), dtype=bool)
        rng = np.random.default_rng(self.seed)
        owners = (
            train.group_by("player_key")
            .agg(pl.col("position_group").cast(pl.String).mode().first())
            .sort("player_key")
        )
        kept: set[str] = set()
        for (_,), rows in owners.group_by(["position_group"], maintain_order=True):
            players = rows["player_key"].to_list()
            n = max(1, round(len(players) * self.sampler.player_fraction))
            kept.update(rng.choice(players, size=n, replace=False).tolist())
        return np.asarray(train["player_key"].is_in(list(kept)).to_numpy(), dtype=bool)

    # --- modèle PyMC -------------------------------------------------------------------

    def _pymc_model(self, data: _Data, weights: np.ndarray) -> Any:
        import pymc as pm  # noqa: PLC0415 - import lourd, seulement pour M2
        import pytensor.tensor as pt  # noqa: PLC0415

        index = self.index_
        if index is None or data.y is None:
            raise RuntimeError("_prepare() doit précéder la construction du modèle")
        coords = {
            "unit": list(index.units),
            "position_group": list(index.groups),
            "position_code": list(index.codes),
            "fixed": list(self.fixed_terms_),
            "player": list(range(len(index.players))),
            "team_season": list(range(len(index.teams))),
        }
        load_mu, load_sd = self.load_prior_
        with pm.Model(coords=coords) as model:
            alpha = pm.Normal("alpha", priors.m2_intercept_mu(), priors.M2_INTERCEPT_SD)
            effect = 0.0
            for level, dim in (
                ("unit", "unit"),
                ("group", "position_group"),
                ("code", "position_code"),
            ):
                sigma = pm.HalfNormal(f"sigma_{level}", priors.M2_SIGMA_POSITION_SD)
                z = pm.Normal(f"z_{level}", 0.0, 1.0, dims=dim)
                if level == "unit":
                    effect = effect + (sigma * z)[index.unit_of_group[index.group_of_code]]
                elif level == "group":
                    effect = effect + (sigma * z)[index.group_of_code]
                else:
                    effect = effect + sigma * z
            position_effect = pm.Deterministic("position_effect", effect, dims="position_code")
            slope_mu = pm.Normal("slope_mu", 0.0, priors.M2_SLOPE_SD)
            slope_sigma = pm.HalfNormal("slope_sigma", priors.M2_SLOPE_SD)
            z_slope = pm.Normal("z_slope", 0.0, 1.0, dims="position_group")
            slope = pm.Deterministic(
                "slope", slope_mu + slope_sigma * z_slope, dims="position_group"
            )
            beta_load = pm.Normal("beta_load", load_mu, load_sd)
            beta = pm.Normal("beta", 0.0, priors.M2_FIXED_SD, dims="fixed")
            sigma_player = pm.HalfNormal("sigma_player", priors.M2_SIGMA_PLAYER_SD)
            z_player = pm.Normal("z_player", 0.0, 1.0, dims="player")
            player_effect = pm.Deterministic(
                "player_effect", sigma_player * z_player, dims="player"
            )
            sigma_team = pm.HalfNormal("sigma_team", priors.M2_SIGMA_TEAM_SD)
            z_team = pm.Normal("z_team", 0.0, 1.0, dims="team_season")
            team_effect = pm.Deterministic("team_effect", sigma_team * z_team, dims="team_season")
            eta = (
                alpha
                + position_effect[data.code]
                + slope[data.group] * data.x_cons
                + beta_load * data.x_load
                + pt.dot(data.X, beta)  # type: ignore[no-untyped-call]
                + player_effect[data.player]
                + team_effect[data.team]
                + data.offset
            )
            lam = pt.exp(eta)
            # Bernoulli cloglog : log h = log(1 - exp(-lam)), log(1 - h) = -lam ; pondérée (IPW).
            loglik = weights * (data.y * pt.log1mexp(-lam) - (1.0 - data.y) * lam)
            pm.Potential("weighted_loglik", loglik.sum())
        return model

    def _incidence_table(self, draws: dict[str, np.ndarray], data: _Data) -> pl.DataFrame:
        """Simulated incidence per position (/1000 h) from parameter draws."""
        index = self.index_
        if index is None:
            raise RuntimeError("fit() requis")
        p = _marginal_hazard(draws, data)
        lo_band, hi_band = priors.M2_PRIOR_INCIDENCE_BAND
        rows = []
        for i, code in enumerate(index.codes):
            mask = data.code == i
            hours = data.minutes[mask].sum() / MINUTES_PER_HOUR
            incidence = PER_1000H * p[:, mask].sum(axis=1) / hours
            q05, q25, q50, q75, q95 = np.quantile(incidence, [0.05, 0.25, 0.5, 0.75, 0.95])
            rows.append(
                {
                    "position_code": code,
                    "q05": q05,
                    "q25": q25,
                    "median": q50,
                    "q75": q75,
                    "q95": q95,
                    "in_band": bool(lo_band <= q50 <= hi_band),
                }
            )
        return pl.DataFrame(rows)

    def prior_incidence(self, train: pl.DataFrame) -> pl.DataFrame:
        """Prior predictive check (docs/06 §2) on the compiled model of `train`."""
        import pymc as pm  # noqa: PLC0415

        data = self._prepare(train)
        model = self._pymc_model(data, np.ones(len(train)))
        with model, warnings.catch_warnings():
            # Attendu : le Potential (vraisemblance) n'intervient pas sous le prior.
            warnings.filterwarnings("ignore", message="The effect of Potentials")
            prior = pm.sample_prior_predictive(
                draws=self.sampler.prior_draws, var_names=list(_DRAW_NAMES), random_seed=self.seed
            )
        draws = _stack(prior.prior, _DRAW_NAMES, self.sampler.prior_draws, self.seed)
        return self._incidence_table(draws, data)

    # --- RiskModel ---------------------------------------------------------------------

    def fit(
        self,
        train: pl.DataFrame,
        valid: pl.DataFrame | None = None,
        eligible: pl.DataFrame | None = None,
    ) -> HierarchicalHazardModel:
        import arviz as az  # noqa: PLC0415
        import pymc as pm  # noqa: PLC0415

        del valid  # pas d'hyperparamètre réglé sur la validation
        weights = np.ones(len(train), dtype=float)
        if self.ipw:
            if eligible is None:
                raise ValueError("M2 avec IPW exige le frame éligible (runner)")
            w, self.ipw_diagnostics_, _, self.warning_ = fit_ipw_weights(
                train,
                eligible,
                selection=SelectionSpec(seed=self.seed),
                stabilize=True,
                truncate=self.truncate,
            )
            if w is not None:
                weights = w
        mask = self._subsample(train)
        train = train.filter(pl.Series(mask))
        weights = weights[mask]
        self.n_train_rows_ = len(train)
        self.prior_incidence_ = self.prior_incidence(train)
        data = self._data(train)
        model = self._pymc_model(data, weights)
        start = time.monotonic()
        with model:
            self.idata_ = pm.sample(
                draws=self.sampler.draws,
                tune=self.sampler.tune,
                chains=self.sampler.chains,
                cores=self.sampler.cores,
                target_accept=self.sampler.target_accept,
                random_seed=self.seed,
                progressbar=False,
                compute_convergence_checks=False,
            )
        seconds = time.monotonic() - start
        free = [v.name for v in model.free_RVs]
        rhat = az.rhat(self.idata_, var_names=free)  # type: ignore[no-untyped-call]
        ess_bulk = az.ess(self.idata_, var_names=free, method="bulk")  # type: ignore[no-untyped-call]
        ess_tail = az.ess(self.idata_, var_names=free, method="tail")  # type: ignore[no-untyped-call]
        self.diagnostics_ = McmcDiagnostics(
            r_hat_max=max(float(rhat[v].max()) for v in free),
            ess_bulk_min=min(float(ess_bulk[v].min()) for v in free),
            ess_tail_min=min(float(ess_tail[v].min()) for v in free),
            divergences=int(self.idata_.sample_stats["diverging"].sum()),
            seconds=seconds,
        )
        self.posterior_ = _Posterior(
            _stack(self.idata_.posterior, _DRAW_NAMES, self.sampler.max_prediction_draws, self.seed)
        )
        source = self.spec.source_columns()
        self.profiles_ = scenario_profiles(
            train,
            [c for c in source if c not in self.spec.categorical],
            [c for c in source if c in self.spec.categorical],
        )
        return self

    def predict_draws(self, df: pl.DataFrame) -> np.ndarray:
        """(draws, rows) posterior hazards, unknown players / team-seasons integrated."""
        if self.posterior_ is None:
            raise RuntimeError("fit() doit être appelé avant predict_proba()")
        return _marginal_hazard(self.posterior_.draws, self._data(df))

    def predict_proba(self, df: pl.DataFrame) -> np.ndarray:
        """Posterior predictive mean of the hazard."""
        return np.asarray(self.predict_draws(df).mean(axis=0), dtype=float)

    def params(self) -> dict[str, Any]:
        d = self.diagnostics_
        w = self.ipw_diagnostics_
        index = self.index_
        return {
            "link": "cloglog",
            "offset": f"log(minutes_played/{EXPOSURE_REF_MINUTES:.0f})",
            "priors_version": priors.PRIORS_VERSION,
            "formula_fixed": self.transform_.formula if self.transform_ else None,
            "dropped_terms": ",".join(self.transform_.dropped) if self.transform_ else None,
            "draws": self.sampler.draws,
            "tune": self.sampler.tune,
            "chains": self.sampler.chains,
            "target_accept": self.sampler.target_accept,
            "fast": self.sampler.fast,
            "player_fraction": self.sampler.player_fraction,
            "n_train_rows": self.n_train_rows_,
            "n_players": len(index.players) if index else None,
            "n_team_seasons": len(index.teams) if index else None,
            "ipw": self.ipw,
            "ipw_enabled": w.ipw_enabled if w else False,
            "r_hat_max": d.r_hat_max if d else None,
            "ess_bulk_min": d.ess_bulk_min if d else None,
            "ess_tail_min": d.ess_tail_min if d else None,
            "divergences": d.divergences if d else None,
            "sampling_seconds": d.seconds if d else None,
            "mcmc_status": self.status,
            "prior_check_ok": self.prior_check_ok,
        }

    @property
    def prior_check_ok(self) -> bool | None:
        if self.prior_incidence_ is None:
            return None
        return bool(self.prior_incidence_["in_band"].all())

    # --- rapport -----------------------------------------------------------------------

    def _summary(self, values: np.ndarray) -> str:
        lo, hi = np.quantile(values, [(1 - CI_LEVEL) / 2, (1 + CI_LEVEL) / 2])
        return f"{values.mean():.3f} [{lo:.3f}; {hi:.3f}]"

    def _effects_table(self) -> str:
        if self.posterior_ is None or self.index_ is None:
            return ""
        d = self.posterior_.draws
        lines = ["| Paramètre | Moyenne [IC90] |", "|---|---|"]
        lines.append(
            f"| alpha (intercept, cloglog / match complet) | {self._summary(d['alpha'])} |"
        )
        for name in ("sigma_player", "sigma_team"):
            lines.append(f"| {name} | {self._summary(d[name])} |")
        lines.append(f"| beta_load (min_28d standardisé) | {self._summary(d['beta_load'])} |")
        for i, group in enumerate(self.index_.groups):
            lines.append(f"| pente {SLOPE_TERM} - {group} | {self._summary(d['slope'][:, i])} |")
        for i, code in enumerate(self.index_.codes):
            lines.append(f"| effet poste - {code} | {self._summary(d['position_effect'][:, i])} |")
        for j, term in enumerate(self.fixed_terms_):
            lines.append(f"| {term} | {self._summary(d['beta'][:, j])} |")
        lo, hi = self.load_prior_
        lines.append(
            f"\nPrior beta_load : Normal({lo:.4f}, {hi:.4f}) = log(1,14) par +3,2 FGE / 30 j"
            " (Williams 2017) mis à l'échelle de l'écart-type de min_28d au train."
            " Association, pas causalité."
        )
        return "\n".join(lines)

    def _diagnostics_table(self) -> str:
        d = self.diagnostics_
        if d is None:
            return ""
        s = self.sampler
        lines = [
            "| Critère | Valeur | Seuil | OK |",
            "|---|---|---|---|",
            f"| R-hat max | {d.r_hat_max:.4f} | ≤ {R_HAT_MAX} | {d.r_hat_max <= R_HAT_MAX} |",
            f"| ESS bulk min | {d.ess_bulk_min:.0f} | ≥ {ESS_MIN:.0f} |"
            f" {d.ess_bulk_min >= ESS_MIN} |",
            f"| ESS tail min | {d.ess_tail_min:.0f} | ≥ {ESS_MIN:.0f} |"
            f" {d.ess_tail_min >= ESS_MIN} |",
            f"| Divergences | {d.divergences} | 0 | {d.divergences == 0} |",
            f"\nStatut : **{self.status}**. {s.chains} chaines, {s.draws} tirages"
            f" ({s.tune} de chauffe), target_accept {s.target_accept},"
            f" {d.seconds / 60:.1f} min d'échantillonnage, {self.n_train_rows_} lignes."
            + (" Mode --fast (exploration, non publiable)." if s.fast else ""),
        ]
        if self.ipw_diagnostics_ is not None:
            w = self.ipw_diagnostics_
            lines.append(
                f"IPW : pente sélection {w.slope:.3f}, actif {w.ipw_enabled},"
                f" ESS/n {w.ess_ratio:.3f}, w max {w.weight_max:.2f}."
                + (f" ⚠ {self.warning_}" if self.warning_ else "")
            )
        return "\n".join(lines)

    def _prior_table(self) -> str:
        if self.prior_incidence_ is None:
            return ""
        lo, hi = priors.M2_PRIOR_INCIDENCE_BAND
        lines = ["| Poste | Médiane | IC50 | IC90 | Dans [30; 150] |", "|---|---|---|---|---|"]
        lines += [
            f"| {r['position_code']} | {r['median']:.1f} | [{r['q25']:.1f}; {r['q75']:.1f}]"
            f" | [{r['q05']:.1f}; {r['q95']:.1f}] | {r['in_band']} |"
            for r in self.prior_incidence_.iter_rows(named=True)
        ]
        lines.append(
            f"\nIncidence simulée sous les priors (/1000 h, exposition du train), critère :"
            f" médiane dans [{lo:.0f}; {hi:.0f}] pour chaque poste."
        )
        return "\n".join(lines)

    def curve_bands(self, scenario: str = "median") -> dict[str, np.ndarray]:
        """Per position: (3, N) = posterior mean, lower, upper (90 % credible) of h(N)."""
        out = {}
        lo_q, hi_q = (1 - CI_LEVEL) / 2, (1 + CI_LEVEL) / 2
        for code in sorted(self.profiles_):
            draws = hazard_curve_draws(self, code, scenario=scenario)
            out[code] = np.vstack(
                [
                    draws.mean(axis=0),
                    np.quantile(draws, lo_q, axis=0),
                    np.quantile(draws, hi_q, axis=0),
                ]
            )
        return out

    def report_tables(self) -> dict[str, str]:
        if self.posterior_ is None:
            return {}
        ns = self.scenarios_.n_range
        idx = [ns.index(n) for n in _TABLE_NS if n in ns]
        bands = self.curve_bands()
        curve_lines = [
            "| Poste | "
            + " | ".join(f"N={ns[i]}" for i in idx)
            + f" | Cumulé {CUMULATIVE_HORIZON} |",
            "|---|" + "---|" * (len(idx) + 1),
        ]
        for code, band in bands.items():
            cells = [f"{band[0, i]:.4f} [{band[1, i]:.4f}; {band[2, i]:.4f}]" for i in idx]
            cum = cumulative_risk(band[0, :CUMULATIVE_HORIZON])
            curve_lines.append(f"| {code} | " + " | ".join(cells) + f" | {cum:.3f} |")
        curve_lines.append(
            "\nh(N) = P(blessure au match suivant | N matchs consécutifs), 80 min, profil médian"
            " du poste, nouveau joueur et nouvelle équipe-saison (effets intégrés)."
            f" Moyenne postérieure [IC{int(CI_LEVEL * 100)} crédible]. Association, pas causalité."
        )
        scenarios = list(self.scenarios_.overrides)
        scenario_lines = [
            "| Poste | " + " | ".join(scenarios) + " |",
            "|---|" + "---|" * len(scenarios),
        ]
        for code in sorted(self.profiles_):
            cells = [f"{_scenario_draws(self, code, s):.3f}" for s in scenarios]
            scenario_lines.append(f"| {code} | " + " | ".join(cells) + " |")
        return {
            "M2 : diagnostics MCMC": self._diagnostics_table(),
            "M2 : prior predictive check": self._prior_table(),
            "M2 : effets (moyenne postérieure, IC90 crédible)": self._effects_table(),
            "Courbes h(N) par poste (scénario médian, IC90 crédible)": "\n".join(curve_lines),
            f"Risque cumulé sur {CUMULATIVE_HORIZON} matchs par scénario": "\n".join(
                scenario_lines
            ),
        }

    def report_figures(self, directory: Path, run_id: str) -> list[Path]:
        if self.posterior_ is None:
            return []
        import matplotlib.pyplot as plt  # noqa: PLC0415 - backend Agg fixé par le runner

        ns = np.asarray(self.scenarios_.n_range)
        fig, ax = plt.subplots(figsize=(8, 5))
        for code, band in self.curve_bands().items():
            (line,) = ax.plot(ns, band[0], label=code)
            ax.fill_between(ns, band[1], band[2], color=line.get_color(), alpha=0.12)
        ax.set_xlabel("N matchs consécutifs")
        ax.set_ylabel("h(N) : P(blessure au match suivant, 80 min)")
        ax.set_title(f"{self.name} - h(N), IC90 crédible (association, non causale)")
        ax.legend(fontsize="small", ncol=3)
        fig.tight_layout()
        path = directory / f"{run_id}_hazard_curves.png"
        fig.savefig(path, dpi=120)
        plt.close(fig)
        return [path]

    def report_artifacts(self, directory: Path, run_id: str) -> list[Path]:
        """Serialized model: ArviZ InferenceData (NetCDF), MLflow artifact (docs/06 §5)."""
        if self.idata_ is None:
            return []
        path = directory / f"{run_id}_idata.nc"
        self.idata_.to_netcdf(str(path))
        return [path]
