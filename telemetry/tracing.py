# telemetry/tracing.py

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol

from telemetry.redaction import safe_attributes

log = logging.getLogger(__name__)


class SpanLike(Protocol):
    def set_attribute(self, key: str, value: Any) -> None: ...
    def add_event(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> None: ...
    def record_exception(self, exception: BaseException) -> None: ...


class NullSpan:
    def set_attribute(self, key: str, value: Any) -> None:
        return None

    def add_event(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        return None

    def record_exception(self, exception: BaseException) -> None:
        return None


class TracingRuntime:
    def __init__(
        self,
        *,
        enabled: bool,
        tracer: Any | None = None,
    ) -> None:
        self._enabled = enabled
        self._tracer = tracer

    @contextmanager
    def span(
        self,
        name: str,
        *,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[SpanLike]:
        if not self._enabled or self._tracer is None:
            yield NullSpan()
            return

        try:
            with self._tracer.start_as_current_span(name) as span:
                for key, value in safe_attributes(
                    attributes or {}
                ).items():
                    span.set_attribute(key, value)

                yield span
        except Exception:
            log.warning(
                "telemetry.span_failure",
                extra={"span_name": name},
                exc_info=True,
            )
            yield NullSpan()
