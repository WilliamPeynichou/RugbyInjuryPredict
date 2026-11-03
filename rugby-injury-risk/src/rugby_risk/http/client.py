import asyncio
from collections.abc import Awaitable, Callable
from importlib.metadata import version
from types import TracebackType
from typing import Self
from urllib.parse import urlsplit

import httpx

from rugby_risk.config.sources import SourceConfig, assert_authorized
from rugby_risk.errors import SourceNotAuthorizedError
from rugby_risk.http.ratelimit import HostRateLimiter
from rugby_risk.http.robots import RobotsCache
from rugby_risk.http.store import FetchResult, RawStore, sha256_of, utcnow
from rugby_risk.http.urls import canonicalize_url
from rugby_risk.settings import Settings, get_settings

TIMEOUT_SECONDS = 30.0
RETRY_STATUSES = {429, 500, 502, 503, 504}
NOT_MODIFIED = 304
MAX_BACKOFF_SECONDS = 60.0


class RobotsDisallowedError(Exception):
    """robots.txt forbids the URL."""


class PoliteClient:
    """Only network entry point: authorized hosts only, rate limited, robots-aware, archived."""

    def __init__(  # noqa: PLR0913 - keyword-only test seams
        self,
        source_id: str,
        settings: Settings | None = None,
        store: RawStore | None = None,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        transport: httpx.AsyncBaseTransport | None = None,
        limiter: HostRateLimiter | None = None,
    ) -> None:
        self.source_id = source_id
        self.settings = settings or get_settings()
        self.store = store or RawStore()
        self._sleep = sleep
        self._transport = transport
        self._source: SourceConfig | None = None
        self._limiter = limiter
        self._robots = RobotsCache()
        self._http: httpx.AsyncClient | None = None

    @property
    def user_agent(self) -> str:
        return f"rugby-risk-research/{version('rugby-injury-risk')} (+{self.settings.http_contact})"

    async def __aenter__(self) -> Self:
        # Guard first: an unauthorized source must never reach the network layer.
        self._source = assert_authorized(self.source_id)
        self._limiter = self._limiter or HostRateLimiter(
            self._source.min_delay_seconds, sleep=self._sleep
        )
        self._http = httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS,
            headers={"User-Agent": self.user_agent},
            transport=self._transport,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._http:
            await self._http.aclose()

    def _allowed_hosts(self, source: SourceConfig) -> set[str]:
        hosts = set(source.extra_hosts)
        if source.base_url is not None:
            hosts.add(source.base_url.host or "")
        return hosts

    async def _check_robots(self, url: str, source: SourceConfig) -> None:
        if not source.respect_robots:
            return
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        parser = self._robots.lookup(origin)
        if parser is None:
            response = await self._request(f"{origin}/robots.txt", None, retry=False)
            self._robots.store(origin, response.status_code, response.text)
            parser = self._robots.lookup(origin)
        if parser is not None and not parser.can_fetch(self.user_agent, url):
            raise RobotsDisallowedError(url)

    async def _request(
        self, url: str, headers: dict[str, str] | None, *, retry: bool = True
    ) -> httpx.Response:
        assert self._http is not None and self._limiter is not None and self._source is not None
        attempts = self._source.max_retries if retry else 0
        for attempt in range(attempts + 1):
            await self._limiter.wait(urlsplit(url).netloc)
            response = await self._http.get(url, headers=headers)
            if response.status_code not in RETRY_STATUSES or attempt == attempts:
                return response
            retry_after = response.headers.get("Retry-After", "")
            delay = float(retry_after) if retry_after.isdigit() else 2.0**attempt
            await self._sleep(min(delay, MAX_BACKOFF_SECONDS))
        raise AssertionError("unreachable")

    async def get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> FetchResult:
        """Fetch `url`. `headers` (e.g. API keys) are sent but never archived."""
        source = assert_authorized(self.source_id)
        full_url = canonicalize_url(url, params)
        if self.settings.offline:
            cached = self.store.get_latest(self.source_id, full_url)
            if cached is None:
                raise FileNotFoundError(f"Not in raw lake (offline): {full_url}")
            return cached
        if urlsplit(full_url).hostname not in self._allowed_hosts(source):
            raise SourceNotAuthorizedError(f"Host not registered for {self.source_id}: {full_url}")
        previous = self.store.latest_row(self.source_id, full_url)
        await self._check_robots(full_url, source)
        sent = dict(headers or {})
        if previous and previous.etag:
            sent["If-None-Match"] = previous.etag
        if previous and previous.last_modified:
            sent["If-Modified-Since"] = previous.last_modified
        response = await self._request(full_url, sent)
        if response.status_code == NOT_MODIFIED:
            cached = self.store.get_latest(self.source_id, full_url)
            if cached is not None:
                return cached
        response.raise_for_status()
        content = response.content
        result = FetchResult(
            source=self.source_id,
            url=full_url,
            status=response.status_code,
            content=content,
            content_type=response.headers.get("content-type", "application/octet-stream"),
            sha256=sha256_of(content),
            fetched_at=utcnow(),
            from_cache=False,
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
        )
        self.store.put(result)
        return result
