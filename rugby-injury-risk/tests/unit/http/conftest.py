import httpx
import pytest

from rugby_risk.config.sources import SourceConfig
from rugby_risk.http import PoliteClient, RawStore
from rugby_risk.http import client as client_module
from rugby_risk.http.ratelimit import HostRateLimiter
from rugby_risk.settings import Settings

pytestmark = pytest.mark.unit


@pytest.fixture
def source(monkeypatch):
    cfg = SourceConfig(
        source_id="demo", authorized=True, base_url="https://demo.test", min_delay_seconds=1.0
    )
    monkeypatch.setattr(client_module, "assert_authorized", lambda _id: cfg)
    return cfg


@pytest.fixture
def sleeps():
    return []


@pytest.fixture
def make_client(source, sleeps, tmp_path):
    def _make(handler, *, offline=False, store=None):
        async def sleep(seconds):
            sleeps.append(seconds)

        return PoliteClient(
            "demo",
            Settings(offline=offline, http_contact="me@x.org"),
            store or RawStore(tmp_path / "raw"),
            sleep=sleep,
            limiter=HostRateLimiter(0.0),
            transport=httpx.MockTransport(handler),
        )

    return _make
