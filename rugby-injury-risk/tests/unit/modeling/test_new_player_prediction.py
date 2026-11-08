"""F22 : prédiction pour joueur / équipe-saison absents du train (intégration Gauss-Hermite)."""

import math

import numpy as np
import polars as pl
import pytest

from rugby_risk.modeling.hierarchical import (
    FAST_SAMPLER,
    HierarchicalHazardModel,
    SamplerConfig,
    _Posterior,
)
from tests.hazard_factory import hierarchical_frame

pytestmark = pytest.mark.unit

N_MC = 300_000
MC_TOLERANCE = 0.005
SIGMA_PLAYER = 0.6


def _fake_posterior(
    model: HierarchicalHazardModel, n_fixed: int, *, sigma_player: float, sigma_team: float
) -> _Posterior:
    """Posterior factice : effets fixes nuls, seuls les sigmas portent l'intégration."""
    index = model.index_
    assert index is not None
    draws = {
        "alpha": np.array([-2.62]),
        "position_effect": np.zeros((1, len(index.codes))),
        "slope": np.zeros((1, len(index.groups))),
        "beta_load": np.zeros(1),
        "beta": np.zeros((1, n_fixed)),
        "sigma_player": np.array([sigma_player]),
        "player_effect": np.zeros((1, len(index.players))),
        "sigma_team": np.array([sigma_team]),
        "team_effect": np.zeros((1, len(index.teams))),
    }
    return _Posterior(draws)


@pytest.fixture(scope="module")
def prepared() -> tuple[HierarchicalHazardModel, pl.DataFrame]:
    """Transform et index appris sur le train, sans MCMC (posterior injecté ensuite)."""
    train = hierarchical_frame(players=120, seasons=1, matches=12, seed=3)
    model = HierarchicalHazardModel(sampler=SamplerConfig(), ipw=False, seed=3)
    model._prepare(train)
    return model, train


def _unknown_rows(train: pl.DataFrame) -> pl.DataFrame:
    """Même ligne que le train mais joueur et équipe-saison jamais vus."""
    return train.head(2).with_columns(
        pl.lit("p_never_seen").alias("player_key"),
        pl.lit("t99").alias("team_id"),
        pl.lit("2099-00").alias("season_id"),
    )


def test_unknown_player_team_prediction_finite(prepared) -> None:
    model, train = prepared
    data = model._data(train)
    model.posterior_ = _fake_posterior(
        model, data.X.shape[1], sigma_player=SIGMA_PLAYER, sigma_team=0.3
    )
    p = model.predict_proba(_unknown_rows(train))
    assert p.shape == (2,)
    assert np.isfinite(p).all()
    assert ((p > 0.0) & (p < 1.0)).all()


def test_integration_matches_monte_carlo(prepared) -> None:
    """Gauss-Hermite (20 nœuds) ≈ Monte Carlo : E_u[h(eta + u)], u ~ N(0, sigma_player²)."""
    model, train = prepared
    rows = _unknown_rows(train).head(1)
    data = model._data(rows)

    model.posterior_ = _fake_posterior(model, data.X.shape[1], sigma_player=0.0, sigma_team=0.0)
    p_base = float(model.predict_draws(rows)[0, 0])  # var = 0 : pas d'intégration

    model.posterior_ = _fake_posterior(
        model, data.X.shape[1], sigma_player=SIGMA_PLAYER, sigma_team=0.0
    )
    p_gh = float(model.predict_draws(rows)[0, 0])

    eta_base = math.log(-math.log(1.0 - p_base))
    rng = np.random.default_rng(0)
    u = rng.normal(0.0, SIGMA_PLAYER, size=N_MC)
    p_mc = float(np.mean(-np.expm1(-np.exp(eta_base + u))))
    assert abs(p_gh - p_mc) < MC_TOLERANCE, (p_gh, p_mc)


def test_unknown_carries_population_variance(prepared) -> None:
    """h() convexe en eta => E[h(eta+u)] > h(eta) : le nouveau joueur porte bien la variance."""
    model, train = prepared
    rows = _unknown_rows(train).head(1)
    data = model._data(rows)

    model.posterior_ = _fake_posterior(model, data.X.shape[1], sigma_player=0.0, sigma_team=0.0)
    p_base = float(model.predict_proba(rows)[0])
    model.posterior_ = _fake_posterior(
        model, data.X.shape[1], sigma_player=SIGMA_PLAYER, sigma_team=0.0
    )
    p_unknown = float(model.predict_proba(rows)[0])
    assert p_unknown > p_base


def test_known_team_unknown_player(prepared) -> None:
    """Équipe-saison connue (effet appris = 0 ici), joueur inconnu : prédiction finie."""
    model, train = prepared
    rows = train.head(1).with_columns(pl.lit("p_never_seen").alias("player_key"))
    data = model._data(rows)
    assert (data.player == -1).all() and (data.team >= 0).all()
    model.posterior_ = _fake_posterior(
        model, data.X.shape[1], sigma_player=SIGMA_PLAYER, sigma_team=0.3
    )
    p = model.predict_proba(rows)
    assert np.isfinite(p).all() and ((p > 0.0) & (p < 1.0)).all()


def test_fast_sampler_flag() -> None:
    assert FAST_SAMPLER.fast is True
    assert SamplerConfig().fast is False
