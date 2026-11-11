"""F26 security: a forbidden key anywhere in a JSON payload becomes a 500, never a leak."""

from typing import Any

import polars as pl
import pytest
from fastapi.testclient import TestClient

from rugby_risk.api.main import create_app
from rugby_risk.api.security import contains_forbidden_key
from rugby_risk.settings import Settings

pytestmark = pytest.mark.unit


class EmptyRepository:
    """Dépôt sans donnée : les routes de test ajoutées n'en lisent pas."""

    def table(self, name: str) -> pl.DataFrame:
        return pl.DataFrame()


@pytest.mark.parametrize(
    "payload",
    [
        {"player_key": "abc"},
        {"outer": {"inner": {"player_key": "abc"}}},
        [{"ok": 1}, {"player_key": "abc"}],
        {"items": [{"deep": [{"player_id": 3}]}]},
        {"Player_Key": "x"},
    ],
)
def test_forbidden_key_detected_at_any_depth(payload: Any) -> None:
    assert contains_forbidden_key(payload)


def test_clean_payload_passes() -> None:
    assert not contains_forbidden_key({"points": [{"p_mean": 0.01}], "warning": "x"})


def test_guard_middleware_blocks_nested_key() -> None:
    app = create_app(repository=EmptyRepository(), settings=Settings())

    @app.get("/v1/leak-test")
    def leak() -> dict[str, Any]:
        return {"rows": [{"nested": {"player_key": "abc"}}]}

    response = TestClient(app).get("/v1/leak-test")
    assert response.status_code == 500
    assert "réponse publique invalide" in response.json()["detail"]
    assert "abc" not in response.text


def test_guard_middleware_keeps_clean_response_identical() -> None:
    app = create_app(repository=EmptyRepository(), settings=Settings())

    @app.get("/v1/clean-test")
    def clean() -> dict[str, Any]:
        return {"rows": [{"p_mean": 0.01}]}

    response = TestClient(app).get("/v1/clean-test")
    assert response.status_code == 200
    assert response.json() == {"rows": [{"p_mean": 0.01}]}
    assert response.headers["cache-control"] == "public, max-age=3600"


def test_openapi_documentation_is_not_blocked() -> None:
    # Le schéma OpenAPI porte une clé `name` (paramètres) : ce n'est pas une donnée.
    response = TestClient(create_app(repository=EmptyRepository(), settings=Settings())).get(
        "/openapi.json"
    )
    assert response.status_code == 200
    assert "paths" in response.json()


def test_data_route_with_nested_key_still_blocked_after_docs_exception() -> None:
    app = create_app(repository=EmptyRepository(), settings=Settings())

    @app.get("/v1/leak-after-docs")
    def leak() -> dict[str, Any]:
        return {"items": [{"nested": {"player_key": "abc"}}]}

    response = TestClient(app).get("/v1/leak-after-docs")
    assert response.status_code == 500
    assert "abc" not in response.text
