"""In-memory IP-based rate limiter using sliding window."""

import time
import asyncio
import logging
from collections import defaultdict

from app.core.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Simple sliding-window rate limiter.

    Tracks request timestamps per IP address. No Redis dependency.
    """

    def __init__(
        self,
        max_requests: int | None = None,
        window_seconds: int | None = None,
    ):
        self.max_requests = max_requests or settings.rate_limit_requests
        self.window_seconds = window_seconds or settings.rate_limit_window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(self, client_ip: str) -> bool:
        """
        Check if a request from the given IP is allowed.

        Returns True if allowed, False if rate limited.
        """
        now = time.time()
        cutoff = now - self.window_seconds

        async with self._lock:
            # Remove expired timestamps
            timestamps = self._requests[client_ip]
            self._requests[client_ip] = [
                t for t in timestamps if t > cutoff
            ]

            # Check limit
            if len(self._requests[client_ip]) >= self.max_requests:
                logger.warning(
                    "Rate limit exceeded for IP %s (%d requests in %ds)",
                    client_ip,
                    len(self._requests[client_ip]),
                    self.window_seconds,
                )
                return False

            # Record this request
            self._requests[client_ip].append(now)
            return True

    async def get_remaining(self, client_ip: str) -> int:
        """Get the number of remaining requests for an IP."""
        now = time.time()
        cutoff = now - self.window_seconds

        async with self._lock:
            timestamps = self._requests[client_ip]
            active = [t for t in timestamps if t > cutoff]
            return max(0, self.max_requests - len(active))

    async def cleanup(self) -> None:
        """Remove all expired entries to free memory."""
        now = time.time()
        cutoff = now - self.window_seconds

        async with self._lock:
            expired_keys = []
            for ip, timestamps in self._requests.items():
                active = [t for t in timestamps if t > cutoff]
                if active:
                    self._requests[ip] = active
                else:
                    expired_keys.append(ip)

            for key in expired_keys:
                del self._requests[key]

    def reset(self) -> None:
        """Clear all recorded request timestamps."""
        self._requests.clear()


# Global rate limiter instance
rate_limiter = RateLimiter()
