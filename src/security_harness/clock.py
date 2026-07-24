"""
Clock utilities — monotonic timing and ISO 8601 timestamps.

Using time.perf_counter() for latency measurement (monotonic, high resolution)
and datetime.now(UTC) for wall-clock timestamps stored in the database.
"""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(UTC)


def utcnow_iso() -> str:
    """Return the current UTC time as an ISO 8601 string (e.g., 2024-01-15T12:00:00+00:00)."""
    return utcnow().isoformat()


def monotonic_ms() -> int:
    """Return the current monotonic time in milliseconds (suitable for latency measurement)."""
    return int(time.perf_counter() * 1000)


@contextmanager
def timed_ms() -> Generator[list[int], None, None]:
    """
    Context manager that measures elapsed wall time in milliseconds.

    Usage:
        with timed_ms() as elapsed:
            do_work()
        print(elapsed[0])  # milliseconds
    """
    result: list[int] = [0]
    start = time.perf_counter()
    try:
        yield result
    finally:
        result[0] = int((time.perf_counter() - start) * 1000)
