import asyncio
import time
from collections.abc import Awaitable, Callable


class HostRateLimiter:
    """Guarantees `min_delay` seconds between two requests to the same host."""

    def __init__(
        self,
        min_delay: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._delay, self._clock, self._sleep = min_delay, clock, sleep
        self._last: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def wait(self, host: str) -> None:
        async with self._locks.setdefault(host, asyncio.Lock()):
            if host in self._last:
                remaining = self._last[host] + self._delay - self._clock()
                if remaining > 0:
                    await self._sleep(remaining)
            self._last[host] = self._clock()
