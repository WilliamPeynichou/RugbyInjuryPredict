"""F20 curves: h(N) monotone when the simulated effect is, cumulative risk exact."""

from pathlib import Path

import numpy as np
import pytest

from rugby_risk.modeling.curves import cumulative_risk, hazard_curve, load_scenarios
from rugby_risk.modeling.hazard import DiscreteHazardModel
from tests.hazard_factory import hazard_frame


@pytest.fixture(scope="module")
def model() -> DiscreteHazardModel:
    df = hazard_frame(players=600, seasons=2, beta_forward=0.12, beta_back=0.0, seed=11)
    return DiscreteHazardModel(curve_replications=0).fit(df)


def test_curve_increasing_for_forwards(model: DiscreteHazardModel) -> None:
    h = hazard_curve(model, "PROP")
    assert len(h) == len(model.scenarios_.n_range)
    assert np.all(np.diff(h) > 0), h
    # Pente simulée exp(0.12 * 15) ~ x6 : la courbe doit au moins tripler sur 0 -> 15.
    assert h[-1] / h[0] > 3


def test_curve_flatter_for_backs(model: DiscreteHazardModel) -> None:
    prop, wing = hazard_curve(model, "PROP"), hazard_curve(model, "WING")
    assert prop[-1] / prop[0] > wing[-1] / wing[0]


def test_scenarios_and_unknowns(model: DiscreteHazardModel) -> None:
    for name in model.scenarios_.overrides:
        assert hazard_curve(model, "LOCK", scenario=name).shape == (16,)
    with pytest.raises(KeyError):
        hazard_curve(model, "LOCK", scenario="nope")
    with pytest.raises(KeyError):
        hazard_curve(model, "WATERBOY")


def test_cumulative_risk() -> None:
    assert cumulative_risk([0.1, 0.2]) == pytest.approx(1 - 0.9 * 0.8)
    assert cumulative_risk([]) == 0.0
    with pytest.raises(ValueError, match="probabilités"):
        cumulative_risk([1.2])


def test_scenarios_file_validated(tmp_path: Path) -> None:
    bad = tmp_path / "s.yaml"
    bad.write_text("minutes_played: 80\nn_min: 0\nn_max: 3\nscenarios:\n  x: {}\n")
    with pytest.raises(ValueError, match="median"):
        load_scenarios(bad)
    typo = tmp_path / "t.yaml"
    typo.write_text(
        "minutes_played: 80\nn_min: 0\nn_max: 3\nscenarios:\n  median: {}\n"
        "  oops: {minutes_played: 10}\n"
    )
    with pytest.raises(ValueError, match="hors design"):
        DiscreteHazardModel(scenarios_path=typo)


def test_report_tables_and_figure(model: DiscreteHazardModel, tmp_path: Path) -> None:
    tables = model.report_tables()
    assert "Courbes h(N) par poste (scénario médian)" in tables
    assert "Comparaison des liens (train, in-sample)" in tables
    assert "PROP" in tables["Courbes h(N) par poste (scénario médian)"]
    (fig,) = model.report_figures(tmp_path, "run")
    assert fig.exists()
