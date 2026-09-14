"""Tests for in-memory rate limiter."""

import asyncio
import time
import pytest
from app.core.rate_limiter import RateLimiter


@pytest.fixture
def limiter():
    """Fresh rate limiter with low limits for testing."""
    return RateLimiter(max_requests=3, window_seconds=10)


@pytest.mark.asyncio
async def test_allows_requests_under_limit(limiter):
    for _ in range(3):
        assert await limiter.is_allowed("1.2.3.4") is True


@pytest.mark.asyncio
async def test_blocks_when_limit_exceeded(limiter):
    for _ in range(3):
        await limiter.is_allowed("1.2.3.4")
    # 4th request should be blocked
    assert await limiter.is_allowed("1.2.3.4") is False


@pytest.mark.asyncio
async def test_different_ips_independent(limiter):
    for _ in range(3):
        await limiter.is_allowed("1.1.1.1")
    # Different IP should still be allowed
    assert await limiter.is_allowed("2.2.2.2") is True


@pytest.mark.asyncio
async def test_remaining_decrements(limiter):
    remaining_before = await limiter.get_remaining("9.9.9.9")
    assert remaining_before == 3
    await limiter.is_allowed("9.9.9.9")
    remaining_after = await limiter.get_remaining("9.9.9.9")
    assert remaining_after == 2


@pytest.mark.asyncio
async def test_window_expiry(limiter):
    """Requests older than window should not count."""
    # Use a very short window limiter
    short_limiter = RateLimiter(max_requests=2, window_seconds=1)
    await short_limiter.is_allowed("3.3.3.3")
    await short_limiter.is_allowed("3.3.3.3")
    # Blocked now
    assert await short_limiter.is_allowed("3.3.3.3") is False
    # Wait for window to expire
    await asyncio.sleep(1.1)
    # Should be allowed again
    assert await short_limiter.is_allowed("3.3.3.3") is True


@pytest.mark.asyncio
async def test_cleanup_removes_expired(limiter):
    await limiter.is_allowed("4.4.4.4")
    await limiter.cleanup()
    # After cleanup (but window hasn't expired), IP still tracked
    remaining = await limiter.get_remaining("4.4.4.4")
    assert remaining == 2  # 1 used, 2 remaining
