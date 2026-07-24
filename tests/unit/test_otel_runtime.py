# tests/unit/test_otel_runtime.py

from telemetry.config import TelemetryConfig
from telemetry.otel_runtime import OTelRuntime


def test_otel_runtime_noop_when_disabled() -> None:
    config = TelemetryConfig(enabled=False)
    runtime = OTelRuntime(config)
    runtime.initialize()
    assert not runtime._initialized
    runtime.shutdown()


def test_otel_runtime_failure_isolated() -> None:
    config = TelemetryConfig(enabled=True, otlp_endpoint="invalid://endpoint")
    runtime = OTelRuntime(config)
    runtime.initialize()
    runtime.shutdown()
