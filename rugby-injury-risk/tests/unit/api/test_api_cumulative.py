"""F26 cumulative: /v1/cumulative reads cum_* at n_consecutive = k - 1 (k matches)."""

import polars as pl
import pytest
from fastapi.testclient import TestClient

from rugby_risk.api.deps import PublicDataUnavailableError
from rugby_risk.api.main import create_app
from rugby_risk.settings import Settings

pytestmark = pytest.mark.unit

VERSION = "m2_test"


def _curve(position: str, scenario: str = "median", horizon: int = 16) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for n in range(horizon):
        rows.append(
            {
                "model_version": VERSION,
                "season_id": "2022-2023",
                "position_code": position,
                "n_consecutive": n,
                "scenario": scenario,
                "p_mean": 0.01,
                "p_low90": 0.005,
                "p_high90": 0.02,
                # cumul exact sur n+1 matchs à hazard constant 0,01
                "cum_mean": 1 - 0.99 ** (n + 1),
                "cum_low90": 0.004 * (n + 1),
                "cum_high90": 0.03 * (n + 1),
                "n_players_support": 40,
                "computed_at": "t",
            }
        )
    return rows


class Repo:
    def __init__(self, horizon: int = 16) -> None:
        self.frame = pl.DataFrame(_curve("PROP", horizon=horizon) + _curve("WING", horizon=horizon))

    def table(self, name: str) -> pl.DataFrame:
        if name != "pred_position_curve":
            raise PublicDataUnavailableError(name)
        return self.frame


def _client(horizon: int = 16) -> TestClient:
    return TestClient(create_app(repository=Repo(horizon), settings=Settings()))


def test_cumulative_reads_point_k_minus_one() -> None:
    response = _client().get("/v1/cumulative", params={"position": "PROP", "k": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["k_matches"] == 5
    assert body["risk_mean"] == pytest.approx(1 - 0.99**5, rel=1e-9)
    assert body["risk_low90"] == pytest.approx(0.004 * 5)
    assert body["risk_high90"] == pytest.approx(0.03 * 5)
    assert body["warning"]


def test_cumulative_k_one_is_first_point() -> None:
    body = _client().get("/v1/cumulative", params={"position": "PROP", "k": 1}).json()
    assert body["risk_mean"] == pytest.approx(0.01)


def test_cumulative_k_sixteen_is_last_point() -> None:
    response = _client().get("/v1/cumulative", params={"position": "PROP", "k": 16})
    assert response.status_code == 200
    assert response.json()["risk_mean"] == pytest.approx(1 - 0.99**16, rel=1e-9)


@pytest.mark.parametrize("k", [0, -1, 17, 100])
def test_cumulative_k_out_of_range_is_422(k: int) -> None:
    response = _client().get("/v1/cumulative", params={"position": "PROP", "k": k})
    assert response.status_code == 422


def test_cumulative_k_beyond_exported_horizon_is_422() -> None:
    # Horizon exporté réduit à 3 points : k=5 n'existe pas dans la table.
    response = _client(horizon=3).get("/v1/cumulative", params={"position": "PROP", "k": 5})
    assert response.status_code == 422


def test_cumulative_invalid_position_is_422() -> None:
    response = _client().get("/v1/cumulative", params={"position": "NOPE", "k": 3})
    assert response.status_code == 422


def test_cumulative_missing_k_is_422() -> None:
    assert _client().get("/v1/cumulative", params={"position": "PROP"}).status_code == 422


def test_cumulative_is_monotone_in_k() -> None:
    client = _client()
    risks = [
        client.get("/v1/cumulative", params={"position": "PROP", "k": k}).json()["risk_mean"]
        for k in range(1, 17)
    ]
    assert risks == sorted(risks)
