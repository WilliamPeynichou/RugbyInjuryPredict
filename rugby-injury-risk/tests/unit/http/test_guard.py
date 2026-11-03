import httpx
import pytest

from rugby_risk.errors import SourceNotAuthorizedError
from rugby_risk.http import PoliteClient, RawStore
from rugby_risk.settings import Settings

pytestmark = pytest.mark.unit


async def test_unauthorized_source_emits_no_call(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200)

    client = PoliteClient(
        "allrugby", Settings(), RawStore(tmp_path), transport=httpx.MockTransport(handler)
    )
    with pytest.raises(SourceNotAuthorizedError):
        async with client:
            pass
    assert calls == []


async def test_unknown_host_refused(make_client):
    calls = []
    client = make_client(lambda r: calls.append(r) or httpx.Response(200))
    async with client:
        with pytest.raises(SourceNotAuthorizedError):
            await client.get("https://evil.test/x")
    assert calls == []


async def test_user_agent_and_offline(make_client):
    seen = []

    def handler(request):
        seen.append(request.headers["user-agent"])
        return httpx.Response(200 if request.url.path != "/robots.txt" else 404, content=b"a")

    async with make_client(handler) as client:
        await client.get("https://demo.test/a")
    assert seen[0].startswith("rugby-risk-research/") and "(+me@x.org)" in seen[0]
    store = client.store
    async with make_client(handler, offline=True, store=store) as off:
        assert (await off.get("https://demo.test/a")).from_cache
        with pytest.raises(FileNotFoundError):
            await off.get("https://demo.test/missing")
