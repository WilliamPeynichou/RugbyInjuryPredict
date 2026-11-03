import asyncio
import json
from datetime import date

import httpx
import pytest

from rugby_risk.config.sources import SourceConfig
from rugby_risk.http import PoliteClient, RawStore
from rugby_risk.http import client as client_module
from rugby_risk.http.ratelimit import HostRateLimiter
from rugby_risk.settings import Settings
from rugby_risk.sources.espn.fetch import fetch_league_year
from rugby_risk.sources.worldrugby.fetch import fetch_period

pytestmark = pytest.mark.unit


def _client(monkeypatch, tmp_path, source_id, base_url, handler):
    cfg = SourceConfig(
        source_id=source_id, authorized=True, base_url=base_url, min_delay_seconds=1.0
    )
    monkeypatch.setattr(client_module, "assert_authorized", lambda _id: cfg)

    async def sleep(_seconds):
        return None

    return PoliteClient(
        source_id,
        Settings(offline=False, http_contact="me@x.org"),
        RawStore(tmp_path / "raw"),
        sleep=sleep,
        limiter=HostRateLimiter(0.0),
        transport=httpx.MockTransport(handler),
    )


def test_worldrugby_pages_and_filters(monkeypatch, tmp_path):
    seen = []

    def handler(request):
        seen.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.path.endswith("/match"):
            page = int(request.url.params["page"])
            content = [
                [
                    {
                        "matchAltId": "a1",
                        "status": "C",
                        "teams": [{"name": "France"}, {"name": "Chile"}],
                    }
                ],
                [
                    {
                        "matchAltId": "a2",
                        "status": "C",
                        "teams": [{"name": "Chile"}, {"name": "Spain"}],
                    }
                ],
            ][page]
            return httpx.Response(200, json={"pageInfo": {"numPages": 2}, "content": content})
        return httpx.Response(200, json={})

    async def run():
        base = "https://api.wr-rims-prod.pulselive.com"
        async with _client(monkeypatch, tmp_path, "worldrugby", base, handler) as client:
            return await fetch_period(client, date(2024, 1, 1), date(2024, 12, 31))

    assert asyncio.run(run()) == ["a1"]  # Chile v Spain hors nations suivies
    assert "/rugby/v3/match/a1/summary" in seen and "/rugby/v3/match/a1/timeline" in seen
    assert not any("a2" in p for p in seen)


def test_espn_keeps_completed_events(monkeypatch, tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.path.endswith("/scoreboard"):
            events = [
                {"id": "1", "status": {"type": {"completed": True}}},
                {"id": "2", "status": {"type": {"completed": False}}},
            ]
            return httpx.Response(200, content=json.dumps({"events": events}))
        return httpx.Response(200, json={"header": {"id": request.url.params["event"]}})

    async def run():
        async with _client(
            monkeypatch, tmp_path, "espn", "https://site.api.espn.com", handler
        ) as client:
            return await fetch_league_year(client, "164205", 2023)

    assert asyncio.run(run()) == ["1"]
