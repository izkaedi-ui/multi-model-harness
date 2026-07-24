"""
Correlation ID generation and propagation.

Every test run and individual execution is tagged with a correlation ID so that
log lines, database rows, and artifact files can be linked without ambiguity.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

# Context variable so the correlation ID is automatically available in all
# async tasks spawned within a run without explicit passing.
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def generate_run_id() -> str:
    """Generate a run-scoped correlation ID. Format: run-<uuid4>."""
    return f"run-{uuid.uuid4().hex}"


def generate_execution_id() -> str:
    """Generate an execution-scoped correlation ID. Format: exec-<uuid4>."""
    return f"exec-{uuid.uuid4().hex}"


def set_current_correlation_id(correlation_id: str) -> None:
    """Bind a correlation ID to the current async context."""
    _correlation_id.set(correlation_id)


def get_current_correlation_id() -> str:
    """
    Return the correlation ID bound to the current async context.

    Returns an empty string if no correlation ID has been set.
    """
    return _correlation_id.get()
