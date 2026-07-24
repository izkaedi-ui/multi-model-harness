# telemetry/context.py

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator
from contextlib import contextmanager


@dataclass(frozen=True, slots=True)
class CorrelationContext:
    run_id: str
    execution_id: str | None = None
    case_id: str | None = None


_current_context: ContextVar[CorrelationContext | None] = ContextVar(
    "harness_correlation_context",
    default=None,
)


def current_context() -> CorrelationContext | None:
    return _current_context.get()


@contextmanager
def correlation_scope(
    context: CorrelationContext,
) -> Iterator[CorrelationContext]:
    token = _current_context.set(context)

    try:
        yield context
    finally:
        _current_context.reset(token)
