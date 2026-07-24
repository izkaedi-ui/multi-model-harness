"""
Base adapter — shared interface and abstract base class.

Every provider adapter must implement ProviderAdapter (Protocol) and may
optionally extend BaseAdapter to inherit retry, timeout, and redaction hooks.
"""

from __future__ import annotations

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

import yaml

from security_harness.clock import timed_ms
from security_harness.errors import (
    ProviderTimeoutError,
    RetryableProviderError,
    NonRetryableProviderError,
)
from security_harness.types import ModelRequest, ModelResponse

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Protocol — the minimal interface every adapter must satisfy
# ---------------------------------------------------------------------------


@runtime_checkable
class ProviderAdapter(Protocol):
    """Minimal interface implemented by all provider adapters."""

    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Send a request to the provider and return a normalised ModelResponse."""
        ...

    async def health_check(self) -> bool:
        """Return True if the provider API is reachable with the configured credentials."""
        ...

    async def close(self) -> None:
        """Release any resources (HTTP connections, SDK clients, etc.)."""
        ...


# ---------------------------------------------------------------------------
# Abstract base — shared retry / timeout / logging logic
# ---------------------------------------------------------------------------


class BaseAdapter(ABC):
    """
    Abstract base class for provider adapters.

    Subclasses must implement:
        _generate_raw(request) -> ModelResponse

    The public generate() method wraps _generate_raw() with:
        - Per-request timeout enforcement
        - Retry on RetryableProviderError
        - Structured logging
        - Latency measurement
    """

    provider_name: str  # Set by subclass

    def __init__(self, retry_config: dict | None = None) -> None:
        if retry_config is None:
            retry_config = self._load_retry_config()
        self._max_attempts: int = retry_config.get("max_attempts", 3)
        self._base_delay: float = retry_config.get("base_delay_seconds", 1.0)
        self._max_delay: float = retry_config.get("max_delay_seconds", 20.0)
        self._backoff: float = retry_config.get("backoff_multiplier", 2.0)
        self._jitter_max: float = retry_config.get("jitter_max_seconds", 2.0)
        self._timeout: float = retry_config.get("per_request_timeout_seconds", 60.0)

    @staticmethod
    def _load_retry_config() -> dict:
        try:
            with open("config/retry.yaml") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            return {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def generate(self, request: ModelRequest) -> ModelResponse:
        """
        Generate a response with retry and timeout.

        Retries on RetryableProviderError up to max_attempts times.
        Raises the final error if all attempts fail.
        """
        attempt = 0
        last_error: Exception | None = None

        while attempt < self._max_attempts:
            attempt += 1
            try:
                with timed_ms() as elapsed:
                    response = await asyncio.wait_for(
                        self._generate_raw(request),
                        timeout=self._timeout,
                    )
                log.info(
                    "generate.success",
                    extra={
                        "provider": self.provider_name,
                        "model": request.model,
                        "attempt": attempt,
                        "latency_ms": elapsed[0],
                    },
                )
                return response

            except asyncio.TimeoutError:
                last_error = ProviderTimeoutError(self.provider_name, self._timeout)
                log.warning(
                    "generate.timeout",
                    extra={
                        "provider": self.provider_name,
                        "model": request.model,
                        "attempt": attempt,
                        "timeout_seconds": self._timeout,
                    },
                )
            except RetryableProviderError as exc:
                last_error = exc
                log.warning(
                    "generate.retryable_error",
                    extra={
                        "provider": self.provider_name,
                        "model": request.model,
                        "attempt": attempt,
                        "error": str(exc),
                    },
                )
            except NonRetryableProviderError:
                raise
            except Exception as exc:
                # Unknown exception — treat as non-retryable to avoid runaway spend
                log.error(
                    "generate.unexpected_error",
                    extra={
                        "provider": self.provider_name,
                        "model": request.model,
                        "attempt": attempt,
                        "error": str(exc),
                    },
                )
                raise

            if attempt < self._max_attempts:
                delay = min(
                    self._base_delay * (self._backoff ** (attempt - 1)),
                    self._max_delay,
                ) + random.uniform(0, self._jitter_max)
                log.info(
                    "generate.retry_delay",
                    extra={"delay_seconds": round(delay, 2), "next_attempt": attempt + 1},
                )
                await asyncio.sleep(delay)

        assert last_error is not None
        raise last_error

    @abstractmethod
    async def _generate_raw(self, request: ModelRequest) -> ModelResponse:
        """Provider-specific implementation. Called by generate() with retry wrapping."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the provider is reachable and the API key is valid."""

    async def close(self) -> None:
        """Override in subclass to release resources (e.g., close HTTP clients)."""
