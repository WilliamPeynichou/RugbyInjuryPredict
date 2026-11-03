from datetime import UTC, datetime

import httpx
import pytest
import zstandard

from rugby_risk import cli
from rugby_risk.http import FetchResult, RawStore
from rugby_risk.http.store import sha256_of

pytestmark = pytest.mark.unit


def _result(content=b"hello", etag=None):
    return FetchResult(
        "demo",
        "https://demo.test/a?b=1",
        200,
        content,
        "text/html",
        sha256_of(content),
        datetime(2025, 3, 4, tzinfo=UTC),
        False,
        etag,
        None,
    )


def test_idempotent_put_and_roundtrip(tmp_path):
    store = RawStore(tmp_path)
    first, second = store.put(_result()), store.put(_result())
    assert first == second
    assert first.parent == tmp_path / "demo" / "2025" / "03"
    assert first.name.endswith(".html.zst")
    assert zstandard.decompress(first.read_bytes()) == b"hello"
    assert len(list(store.iter_manifest("demo"))) == 2
    assert list(store.iter_manifest("other")) == []
    assert store.get_latest("demo", "https://demo.test/a?b=1").content == b"hello"
    assert store.get_latest("demo", "https://demo.test/zzz") is None


def test_append_only(tmp_path):
    store = RawStore(tmp_path)
    path = store.put(_result())
    path.write_bytes(zstandard.compress(b"tampered"))
    with pytest.raises(FileExistsError):
        store.put(_result())
    with pytest.raises(ValueError, match="sha256"):
        store.put(_result().__class__(**{**_result().__dict__, "content": b"other"}))


def test_empty_manifest(tmp_path):
    assert list(RawStore(tmp_path).iter_manifest()) == []


async def test_304_served_from_lake(make_client, tmp_path):
    seen = []

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        seen.append(request.headers.get("if-none-match"))
        if request.headers.get("if-none-match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(200, content=b"body", headers={"etag": '"v1"'})

    async with make_client(handler) as client:
        fresh = await client.get("https://demo.test/a")
        cached = await client.get("https://demo.test/a")
    assert not fresh.from_cache and cached.from_cache and cached.content == b"body"
    assert seen == [None, '"v1"']
    assert len(list(client.store.iter_manifest())) == 1


def test_cli_ls(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    RawStore(tmp_path / "data" / "raw").put(_result())
    assert cli.main(["raw", "ls", "--source", "demo"]) == 0
    assert "demo https://demo.test/a?b=1" in capsys.readouterr().out
