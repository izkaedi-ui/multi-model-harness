"""
Per-provider async rate limiter using a token bucket algorithm.

Each provider gets an independent bucket seeded from providers.yaml.
The rate limiter is consulted before every request dispatch so that
burst concurrency cannot exceed provider-level throughput limits.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

import yaml

log = logging.getLogger(__name__)


@dataclass
class _Bucket:
    """Simple token bucket for a single provider."""

    requests_per_minute: int
    tokens: float = field(init=False)
    last_refill: float = field(default_factory=time.monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        self.tokens = float(self.requests_per_minute)

    @property
    def refill_rate(self) -> float:
        """Tokens added per second."""
        return self.requests_per_minute / 60.0

    async def acquire(self) -> None:
        """Wait until a token is available, then consume one."""
        while True:
            async with self.lock:
                now = time.monotonic()
                elapsed = now - self.last_refill
                self.tokens = min(
                    float(self.requests_per_minute),
                    self.tokens + elapsed * self.refill_rate,
                )
                self.last_refill = now

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return

                # Calculate how long to wait for next token
                wait = (1.0 - self.tokens) / self.refill_rate

            log.debug(
                "rate_limiter.waiting",
                extra={"wait_seconds": round(wait, 2)},
            )
            await asyncio.sleep(wait)


class RateLimiter:
    """
    Per-provider rate limiter.

    Usage:
        limiter = RateLimiter.from_config()
        await limiter.acquire("openai")
        # ... dispatch request
    """

    def __init__(self, buckets: dict[str, _Bucket]) -> None:
        self._buckets = buckets

    @classmethod
    def from_config(cls, config_path: str = "config/providers.yaml") -> RateLimiter:
        """Build a RateLimiter from providers.yaml."""
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
        except FileNotFoundError:
            log.warning("rate_limiter: providers.yaml not found; using defaults (60 RPM)")
            config = {}

        buckets: dict[str, _Bucket] = {}
        for provider, settings in config.items():
            rpm = settings.get("requests_per_minute", 60)
            if rpm > 0:
                buckets[provider] = _Bucket(requests_per_minute=rpm)

        return cls(buckets)

    async def acquire(self, provider: str) -> None:
        """Acquire a request slot for the given provider."""
        bucket = self._buckets.get(provider)
        if bucket is None:
            return  # No limit configured for this provider
        await bucket.acquire()
