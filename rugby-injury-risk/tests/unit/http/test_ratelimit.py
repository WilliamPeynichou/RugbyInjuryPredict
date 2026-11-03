import pytest

from rugby_risk.http.ratelimit import HostRateLimiter

pytestmark = pytest.mark.unit


async def test_spacing_between_same_host_requests():
    now, slept = [0.0], []

    async def sleep(seconds):
        slept.append(seconds)
        now[0] += seconds

    limiter = HostRateLimiter(3.0, clock=lambda: now[0], sleep=sleep)
    await limiter.wait("a")
    now[0] += 1.0
    await limiter.wait("a")
    await limiter.wait("b")
    assert slept == [2.0]
