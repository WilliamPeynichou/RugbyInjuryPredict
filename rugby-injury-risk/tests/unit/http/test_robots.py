import httpx
import pytest

from rugby_risk.http import RobotsDisallowedError
from rugby_risk.http.robots import RobotsCache

pytestmark = pytest.mark.unit


async def test_disallowed_url_refused(make_client):
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private")
        return httpx.Response(200, content=b"ok")

    async with make_client(handler) as client:
        await client.get("https://demo.test/public")
        with pytest.raises(RobotsDisallowedError):
            await client.get("https://demo.test/private/x")
    assert "/private/x" not in paths
    assert paths.count("/robots.txt") == 1  # cached


def test_status_rules_and_ttl():
    now = [0.0]
    cache = RobotsCache(clock=lambda: now[0])
    cache.store("o", 403, "")
    assert not cache.lookup("o").can_fetch("x", "http://o/a")
    cache.store("o", 404, "")
    assert cache.lookup("o").can_fetch("x", "http://o/a")
    now[0] = 24 * 3600 + 1
    assert cache.lookup("o") is None
