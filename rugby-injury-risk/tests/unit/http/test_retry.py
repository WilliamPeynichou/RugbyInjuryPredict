import httpx
import pytest

pytestmark = pytest.mark.unit


def _handler(statuses, headers=None):
    seq, calls = list(statuses), []

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        calls.append(request)
        return httpx.Response(seq.pop(0), content=b"x", headers=headers or {})

    return handler, calls


async def test_503_then_200(make_client, sleeps):
    handler, calls = _handler([503, 200], {"Retry-After": "7"})
    async with make_client(handler) as client:
        assert (await client.get("https://demo.test/a")).status == 200
    assert len(calls) == 2
    assert sleeps == [7.0]


async def test_exponential_backoff_then_give_up(make_client, sleeps):
    handler, calls = _handler([500, 500, 500, 500])
    async with make_client(handler) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.get("https://demo.test/a")
    assert len(calls) == 4 and sleeps == [1.0, 2.0, 4.0]


async def test_404_no_retry(make_client, sleeps):
    handler, calls = _handler([404])
    async with make_client(handler) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.get("https://demo.test/a")
    assert len(calls) == 1 and sleeps == []
