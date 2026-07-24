"""
Retry manager — classifies exceptions and applies exponential backoff.

Uses retry.yaml to determine which HTTP status codes and exception types
are safe to retry.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Callable, Coroutine, TypeVar

import yaml

from security_harness.errors import NonRetryableProviderError, RetryableProviderError

log = logging.getLogger(__name__)
T = TypeVar("T")


class RetryManager:
    """Wraps an async callable with retry-on-transient-error logic."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 20.0,
        backoff: float = 2.0,
        jitter_max: float = 2.0,
    ) -> None:
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._backoff = backoff
        self._jitter_max = jitter_max

    @classmethod
    def from_config(cls, config_path: str = "config/retry.yaml") -> "RetryManager":
        try:
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}
        except FileNotFoundError:
            cfg = {}
        return cls(
            max_attempts=cfg.get("max_attempts", 3),
            base_delay=cfg.get("base_delay_seconds", 1.0),
            max_delay=cfg.get("max_delay_seconds", 20.0),
            backoff=cfg.get("backoff_multiplier", 2.0),
            jitter_max=cfg.get("jitter_max_seconds", 2.0),
        )

    async def execute(
        self,
        fn: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute fn with retry on RetryableProviderError."""
        attempt = 0
        last_exc: Exception | None = None

        while attempt < self._max_attempts:
            attempt += 1
            try:
                return await fn(*args, **kwargs)
            except NonRetryableProviderError:
                raise
            except RetryableProviderError as exc:
                last_exc = exc
                if attempt < self._max_attempts:
                    delay = min(
                        self._base_delay * (self._backoff ** (attempt - 1)),
                        self._max_delay,
                    ) + random.uniform(0, self._jitter_max)
                    log.warning("retry_manager.retry",
                                extra={"attempt": attempt, "delay": round(delay, 2)})
                    await asyncio.sleep(delay)

        assert last_exc is not None
        raise last_exc
