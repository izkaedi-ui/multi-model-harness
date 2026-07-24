# telemetry/exporters.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ExporterConfig:
    exporter_type: str = "otlp"
    endpoint: str | None = "localhost:4317"
    insecure: bool = True
    timeout_seconds: float = 10.0


def create_exporter(config: ExporterConfig) -> Any:
    if config.exporter_type == "otlp":
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            return OTLPSpanExporter(
                endpoint=config.endpoint,
                insecure=config.insecure,
                timeout=config.timeout_seconds,
            )
        except ImportError:
            return None
    return None
