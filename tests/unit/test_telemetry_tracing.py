# tests/unit/test_telemetry_tracing.py

from telemetry.tracing import TracingRuntime, NullSpan


def test_telemetry_failure_does_not_break_execution() -> None:
    class BrokenTracer:
        def start_as_current_span(self, name: str):
            raise RuntimeError("collector unavailable")

    runtime = TracingRuntime(
        enabled=True,
        tracer=BrokenTracer(),
    )

    with runtime.span("test") as span:
        span.set_attribute("safe", "value")


def test_null_span_noop() -> None:
    runtime = TracingRuntime(enabled=False)
    with runtime.span("test") as span:
        assert isinstance(span, NullSpan)
        span.set_attribute("key", "value")
        span.add_event("event")
        span.record_exception(ValueError("error"))
