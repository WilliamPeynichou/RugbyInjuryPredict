import time
from collections.abc import Callable
from urllib.robotparser import RobotFileParser

ROBOTS_TTL_SECONDS = 24 * 3600
HTTP_UNAUTHORIZED, HTTP_FORBIDDEN, HTTP_ERROR = 401, 403, 400


class RobotsCache:
    """robots.txt per origin, cached 24 h. 401/403 = disallow all, other 4xx = allow all."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._cache: dict[str, tuple[float, RobotFileParser]] = {}

    def lookup(self, origin: str) -> RobotFileParser | None:
        entry = self._cache.get(origin)
        if entry and self._clock() - entry[0] < ROBOTS_TTL_SECONDS:
            return entry[1]
        return None

    def store(self, origin: str, status: int, body: str) -> None:
        parser = RobotFileParser()
        if status in (HTTP_UNAUTHORIZED, HTTP_FORBIDDEN):
            parser.parse(["User-agent: *", "Disallow: /"])
        elif status >= HTTP_ERROR:
            parser.parse([])
        else:
            parser.parse(body.splitlines())
        self._cache[origin] = (self._clock(), parser)
