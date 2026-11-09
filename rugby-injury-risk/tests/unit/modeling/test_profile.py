"""F30 : simulateur de profil par poste (sans MCMC : posterior factice injecté)."""

import dataclasses
import itertools

import numpy as np
import pytest

from rugby_risk.modeling.curves import scenario_profiles
from rugby_risk.modeling.hierarchical import (
    FIXED_SPEC,
    HierarchicalHazardModel,
    McmcDiagnostics,
    SamplerConfig,
    _Posterior,
)
from rugby_risk.modeling.profile import (
    NOT_PROMOTED,
    WARNING,
    PositionProfile,
    ProfileError,
    profile_markdown,
    simulate,
)
from tests.hazard_factory import hierarchical_frame

pytestmark = pytest.mark.unit

OK_DIAG = McmcDiagnostics(
    r_hat_max=1.0, ess_bulk_min=1000.0, ess_tail_min=1000.0, divergences=0, seconds=1.0
)
NAME_FIELDS = {"name", "full_name", "player", "player_key", "player_id"}


def fitted_model(slope: float = 0.2, n_draws: int = 200) -> HierarchicalHazardModel:
    """Transform, index et profils appris sur un train synthétique ; posterior factice."""
    train = hierarchical_frame(players=120, seasons=1, matches=12, seed=3)
    model = HierarchicalHazardModel(sampler=SamplerConfig(), ipw=False, seed=3)
    data = model._prepare(train)
    index = model.index_
    assert index is not None
    rng = np.random.default_rng(0)
    model.posterior_ = _Posterior(
        {
            "alpha": rng.normal(-3.5, 0.1, n_draws),
            "position_effect": rng.normal(0, 0.1, (n_draws, len(index.codes))),
            "slope": np.full((n_draws, len(index.groups)), slope),
            "beta_load": np.zeros(n_draws),
            "beta": np.zeros((n_draws, data.X.shape[1])),
            "sigma_player": np.full(n_draws, 0.5),
            "player_effect": np.zeros((n_draws, len(index.players))),
            "sigma_team": np.full(n_draws, 0.2),
            "team_effect": np.zeros((n_draws, len(index.teams))),
        }
    )
    source = FIXED_SPEC.source_columns()
    model.profiles_ = scenario_profiles(
        train,
        [c for c in source if c not in FIXED_SPEC.categorical],
        [c for c in source if c in FIXED_SPEC.categorical],
    )
    model.diagnostics_ = OK_DIAG
    return model


@pytest.fixture(scope="module")
def model() -> HierarchicalHazardModel:
    return fitted_model()


def test_bands_ordered_and_cumulative_monotone(model) -> None:
    result = simulate(model, PositionProfile("FLY_HALF", horizon=6))
    assert result.ns == (0, 1, 2, 3, 4, 5)
    for band in (*result.per_match, *result.cumulative):
        assert 0.0 < band.low <= band.mean <= band.high < 1.0
    cum = [b.mean for b in result.cumulative]
    assert all(b > a for a, b in itertools.pairwise(cum))
    assert result.cumulative[0].mean == pytest.approx(result.per_match[0].mean)


def test_positive_slope_gives_factor_above_one(model) -> None:
    result = simulate(model, PositionProfile("PROP", horizon=4))
    assert result.factor is not None
    assert result.factor.low > 1.0
    flat = simulate(fitted_model(slope=0.0), PositionProfile("PROP", horizon=4))
    assert flat.factor is not None
    assert flat.factor.mean == pytest.approx(1.0)


def test_fewer_minutes_lower_risk(model) -> None:
    full = simulate(model, PositionProfile("WING", minutes_per_match=80, horizon=1))
    sub = simulate(model, PositionProfile("WING", minutes_per_match=20, horizon=1))
    assert sub.per_match[0].mean < full.per_match[0].mean
    assert full.factor is None


def test_extrapolated_n_flagged(model) -> None:
    result = simulate(model, PositionProfile("LOCK", start_consecutive=40, horizon=2))
    assert result.extrapolated == (40, 41)


@pytest.mark.parametrize(
    "profile",
    [
        PositionProfile("NOT_A_POSITION"),
        PositionProfile("LOCK", horizon=0),
        PositionProfile("LOCK", minutes_per_match=90),
        PositionProfile("LOCK", min_28d=-1),
        PositionProfile("LOCK", start_consecutive=-1),
    ],
)
def test_invalid_profiles_rejected(model, profile) -> None:
    with pytest.raises(ProfileError):
        simulate(model, profile)


def test_failed_mcmc_refused() -> None:
    bad = fitted_model()
    bad.diagnostics_ = dataclasses.replace(OK_DIAG, divergences=3)
    with pytest.raises(ProfileError, match="MCMC"):
        simulate(bad, PositionProfile("LOCK"))


def test_profile_has_no_identifier_field() -> None:
    fields = {f.name for f in dataclasses.fields(PositionProfile)}
    assert not fields & NAME_FIELDS


def test_markdown_warning_bands_and_promotion(model) -> None:
    result = simulate(model, PositionProfile("CENTRE", apps_20min_365d=22, horizon=3))
    meta = {"run_id": "r", "dataset_version": "v", "seasons": ["2020-2021"], "git_sha": "x"}
    md = profile_markdown(result, model, meta, promoted=False)
    assert WARNING in md and NOT_PROMOTED in md
    assert "IC90" in md and "Facteur multiplicatif" in md
    assert "| Matchs ≥ 20 min sur 365 j (club + sélection) | 22 |" in md
    assert "p0" not in md  # aucune clé joueur
    assert NOT_PROMOTED not in profile_markdown(result, model, meta, promoted=True)
