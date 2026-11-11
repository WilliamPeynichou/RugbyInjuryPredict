"""F26 API routes: every endpoint on a fake repository, 422/404/503 paths, Cache-Control."""

from typing import Any

import polars as pl
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rugby_risk.api.deps import PublicDataUnavailableError
from rugby_risk.api.main import create_app
from rugby_risk.settings import Settings

pytestmark = pytest.mark.unit

POSITIONS = ["PROP", "HOOKER", "FLY_HALF", "WING"]
SCENARIOS = ["median", "international_november", "return_from_injury", "short_turnaround_block"]
VERSION = "m2_test-20260101T000000Z"


def _curve_rows() -> pl.DataFrame:
    records: list[dict[str, Any]] = []
    for position in POSITIONS:
        for scenario in SCENARIOS:
            for n in range(16):
                base = 0.01 + 0.001 * n
                records.append(
                    {
                        "model_version": VERSION,
                        "season_id": "2022-2023",
                        "position_code": position,
                        "n_consecutive": n,
                        "scenario": scenario,
                        "p_mean": base,
                        "p_low90": base / 2,
                        "p_high90": base * 2,
                        "cum_mean": 1 - (1 - base) ** (n + 1),
                        "cum_low90": 0.005,
                        "cum_high90": 0.2,
                        "n_players_support": 50,
                        "computed_at": "2026-01-01T00:00:00",
                    }
                )
    return pl.DataFrame(records)


def _season_rows() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "model_version": [VERSION, VERSION],
            "season_id": ["2022-2023", "2023-2024"],
            "position_code": ["PROP", "PROP"],
            "position_group": ["front_row", "front_row"],
            "incidence_per_1000h": [12.5, float("nan")],
            "incidence_low90": [8.0, 0.0],
            "incidence_high90": [18.0, 0.0],
            "injuries_count_bucket": ["10-24", "10-24"],
            "exposure_hours": [900.0, 880.0],
            "n_matches_played": [700, 690],
            "n_players_support": [40, 38],
            "computed_at": ["t", "t"],
        }
    )


def _calibration_rows() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "model_version": [VERSION],
            "test_season": ["2024-2025"],
            "position_group": ["all"],
            "bin": [0],
            "p_pred_mean": [0.002],
            "p_obs": [0.03],
            "n": [782],
            "n_players_support": [315],
        }
    )


def _registry_rows() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "model_version": [VERSION],
            "model_name": ["m2_hierarchical"],
            "role": ["principale"],
            "promoted": [False],
            "trained_at": ["2026-01-01"],
            "train_seasons": ["2022-2023"],
            "test_season": ["2024-2025"],
            "dataset_version": ["7d004d9a146715b139e501738e58620a"],
            "n_test": [7819],
            "brier": [0.0177],
            "brier_low90": [None],
            "brier_high90": [0.0197],
            "brier_skill": [None],
            "logloss": [0.0997],
            "auc_roc": [0.48],
            "calib_slope": [None],
            "notes": ["non promu"],
        }
    )


class FakeRepository:
    def __init__(self, tables: dict[str, pl.DataFrame]) -> None:
        self.tables = tables

    def table(self, name: str) -> pl.DataFrame:
        if name not in self.tables:
            raise PublicDataUnavailableError(f"table absente : {name}")
        return self.tables[name]


@pytest.fixture
def client() -> TestClient:
    repository = FakeRepository(
        {
            "pred_position_curve": _curve_rows(),
            "pred_position_season": _season_rows(),
            "calibration_public": _calibration_rows(),
            "model_registry_public": _registry_rows(),
        }
    )
    app: FastAPI = create_app(repository=repository, settings=Settings())
    return TestClient(app)


def test_health_at_root(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_models(client: TestClient) -> None:
    response = client.get("/v1/models")
    assert response.status_code == 200
    body = response.json()
    assert body[0]["model_version"] == VERSION
    assert body[0]["brier_low90"] is None  # NaN -> null, jamais NaN dans le JSON
    assert body[0]["promoted"] is False


def test_positions(client: TestClient) -> None:
    response = client.get("/v1/positions")
    assert response.status_code == 200
    codes = {row["position_code"] for row in response.json()}
    assert codes == {
        "PROP",
        "HOOKER",
        "LOCK",
        "BACK_ROW",
        "SCRUM_HALF",
        "FLY_HALF",
        "CENTRE",
        "WING",
        "FULLBACK",
    }


def test_scenarios(client: TestClient) -> None:
    response = client.get("/v1/scenarios")
    assert response.status_code == 200
    assert [s["scenario"] for s in response.json()] == SCENARIOS


def test_curve_default_scenario(client: TestClient) -> None:
    response = client.get("/v1/curves", params={"position": "FLY_HALF"})
    assert response.status_code == 200
    body = response.json()
    assert body["position_code"] == "FLY_HALF"
    assert body["scenario"] == "median"
    assert len(body["points"]) == 16
    assert body["warning"]
    assert response.headers["cache-control"] == "public, max-age=3600"


def test_curve_with_model_version(client: TestClient) -> None:
    response = client.get(
        "/v1/curves",
        params={"position": "PROP", "scenario": "return_from_injury", "model_version": VERSION},
    )
    assert response.status_code == 200
    assert response.json()["scenario"] == "return_from_injury"


def test_curve_unknown_version_is_404(client: TestClient) -> None:
    response = client.get("/v1/curves", params={"position": "PROP", "model_version": "absent"})
    assert response.status_code == 404


def test_curve_invalid_position_is_422(client: TestClient) -> None:
    assert client.get("/v1/curves", params={"position": "NOPE"}).status_code == 422


def test_curve_invalid_scenario_is_422(client: TestClient) -> None:
    response = client.get("/v1/curves", params={"position": "PROP", "scenario": "inconnu"})
    assert response.status_code == 422


def test_compare_two_positions(client: TestClient) -> None:
    response = client.get("/v1/curves/compare", params={"positions": "PROP,WING"})
    assert response.status_code == 200
    assert [c["position_code"] for c in response.json()] == ["PROP", "WING"]
    assert all(c["warning"] for c in response.json())


@pytest.mark.parametrize("positions", ["PROP", "PROP,WING,HOOKER,FLY_HALF,WING", "PROP,NOPE"])
def test_compare_bad_count_or_position_is_422(client: TestClient, positions: str) -> None:
    response = client.get("/v1/curves/compare", params={"positions": positions})
    assert response.status_code == 422


def test_compare_invalid_scenario_is_422(client: TestClient) -> None:
    response = client.get(
        "/v1/curves/compare", params={"positions": "PROP,WING", "scenario": "inconnu"}
    )
    assert response.status_code == 422


def test_incidence_all_seasons_nan_is_null(client: TestClient) -> None:
    response = client.get("/v1/incidence")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[1]["incidence_per_1000h"] is None


def test_incidence_one_season(client: TestClient) -> None:
    response = client.get("/v1/incidence", params={"season": "2022-2023"})
    assert response.status_code == 200
    assert [row["season_id"] for row in response.json()] == ["2022-2023"]


def test_incidence_unknown_season_is_404(client: TestClient) -> None:
    assert client.get("/v1/incidence", params={"season": "1999-2000"}).status_code == 404


def test_calibration(client: TestClient) -> None:
    response = client.get("/v1/calibration", params={"model_version": VERSION})
    assert response.status_code == 200
    assert response.json()[0]["n"] == 782


def test_calibration_unknown_version_is_404(client: TestClient) -> None:
    assert client.get("/v1/calibration", params={"model_version": "absent"}).status_code == 404


def test_missing_table_is_503_with_message() -> None:
    app = create_app(repository=FakeRepository({}), settings=Settings())
    client = TestClient(app)
    response = client.get("/v1/curves", params={"position": "PROP"})
    assert response.status_code == 503
    assert "absente" in response.json()["detail"]


def test_cache_control_only_on_200(client: TestClient) -> None:
    assert client.get("/v1/scenarios").headers["cache-control"] == "public, max-age=3600"
    assert "cache-control" not in client.get("/v1/curves", params={"position": "NOPE"}).headers


def test_cors_allows_front_origin_only_for_get() -> None:
    settings = Settings(front_origin="https://front.example")
    client = TestClient(create_app(repository=FakeRepository({}), settings=settings))
    response = client.get("/health", headers={"Origin": "https://front.example"})
    assert response.headers["access-control-allow-origin"] == "https://front.example"
    other = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers
