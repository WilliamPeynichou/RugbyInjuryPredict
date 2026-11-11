"""F26 data access: Supabase repository uses the anon key only; preview files and 503 paths."""

from pathlib import Path

import httpx
import polars as pl
import pytest
import respx

from rugby_risk.api.deps import (
    PreviewRepository,
    PublicDataUnavailableError,
    SupabaseRepository,
)
from rugby_risk.api.main import repository_from_settings
from rugby_risk.settings import Settings

pytestmark = pytest.mark.unit

URL = "https://example.supabase.co"
ANON = "anon-public-key"
SERVICE = "service-role-secret"


@respx.mock
def test_supabase_repository_sends_anon_key_only() -> None:
    route = respx.get(f"{URL}/rest/v1/model_registry_public").mock(
        return_value=httpx.Response(200, json=[{"model_version": "m", "promoted": False}])
    )
    frame = SupabaseRepository(URL, ANON).table("model_registry_public")
    assert frame.height == 1
    sent = route.calls.last.request
    assert sent.headers["apikey"] == ANON
    assert SERVICE not in str(sent.headers)


@respx.mock
def test_supabase_http_error_is_unavailable() -> None:
    respx.get(f"{URL}/rest/v1/pred_position_curve").mock(return_value=httpx.Response(500))
    with pytest.raises(PublicDataUnavailableError):
        SupabaseRepository(URL, ANON).table("pred_position_curve")


@respx.mock
def test_supabase_network_error_is_unavailable() -> None:
    respx.get(f"{URL}/rest/v1/pred_position_curve").mock(side_effect=httpx.ConnectError("x"))
    with pytest.raises(PublicDataUnavailableError):
        SupabaseRepository(URL, ANON).table("pred_position_curve")


def test_settings_with_url_but_no_anon_key_stays_on_preview() -> None:
    settings = Settings(supabase_url=URL, supabase_service_key=SERVICE)
    assert isinstance(repository_from_settings(settings), PreviewRepository)


def test_settings_with_anon_key_uses_supabase() -> None:
    settings = Settings(supabase_url=URL, supabase_anon_key=ANON, supabase_service_key=SERVICE)
    repository = repository_from_settings(settings)
    assert isinstance(repository, SupabaseRepository)
    assert repository.anon_key == ANON


def test_preview_missing_file_is_unavailable(tmp_path: Path) -> None:
    with pytest.raises(PublicDataUnavailableError, match="publish-public"):
        PreviewRepository(directory=tmp_path).table("pred_position_curve")


def test_preview_reads_csv_and_guards(tmp_path: Path) -> None:
    directory = tmp_path
    pl.DataFrame({"position_code": ["PROP"], "n_players_support": [12]}).write_csv(
        directory / "pred_position_season.csv"
    )
    frame = PreviewRepository(directory=directory).table("pred_position_season")
    assert frame["position_code"].to_list() == ["PROP"]
