# telemetry/otel_runtime.py

from __future__ import annotations

import logging
from typing import Any

from telemetry.config import TelemetryConfig
from telemetry.metrics import MetricsRuntime
from telemetry.tracing import TracingRuntime, NullSpan

log = logging.getLogger(__name__)


class OTelRuntime:
    def __init__(self, config: TelemetryConfig) -> None:
        self.config = config
        self._tracer_provider: Any = None
        self._meter_provider: Any = None
        self._initialized = False

    def initialize(self) -> None:
        if not self.config.enabled or self._initialized:
            return

        try:
            from opentelemetry import trace, metrics
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

            resource = Resource.create({
                "service.name": self.config.service_name,
                "service.version": self.config.service_version,
            })

            # Tracing Setup
            if self.config.traces_enabled and self.config.otlp_endpoint:
                span_exporter = OTLPSpanExporter(endpoint=self.config.otlp_endpoint, insecure=True)
                tracer_provider = TracerProvider(resource=resource)
                tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
                trace.set_tracer_provider(tracer_provider)
                self._tracer_provider = tracer_provider

            # Metrics Setup
            if self.config.metrics_enabled and self.config.otlp_endpoint:
                metric_exporter = OTLPMetricExporter(endpoint=self.config.otlp_endpoint, insecure=True)
                reader = PeriodicExportingMetricReader(
                    metric_exporter,
                    export_interval_millis=int(self.config.export_interval_seconds * 1000)
                )
                meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
                metrics.set_meter_provider(meter_provider)
                self._meter_provider = meter_provider

            self._initialized = True
            log.info("telemetry.otel_initialized", extra={"otlp_endpoint": self.config.otlp_endpoint})
        except Exception:
            log.warning("telemetry.otel_initialization_failed", exc_info=True)

    def shutdown(self) -> None:
        if not self._initialized:
            return

        try:
            if self._tracer_provider is not None:
                self._tracer_provider.shutdown()
            if self._meter_provider is not None:
                self._meter_provider.shutdown()
        except Exception:
            log.warning("telemetry.otel_shutdown_failed", exc_info=True)
