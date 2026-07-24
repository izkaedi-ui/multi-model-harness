# telemetry/config.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class TelemetryConfig:
    enabled: bool = False
    service_name: str = "multi-model-harness"
    service_version: str = "unknown"
    otlp_endpoint: str | None = None
    metrics_enabled: bool = False
    traces_enabled: bool = False
    export_interval_seconds: float = 15.0

    def __post_init__(self) -> None:
        if not self.service_name.strip():
            raise ValueError("service_name must not be empty")

        if self.export_interval_seconds <= 0:
            raise ValueError(
                "export_interval_seconds must be greater than zero"
            )


def load_telemetry_config(
    values: Mapping[str, object] | None = None,
) -> TelemetryConfig:
    import os

    vals = dict(values) if values else {}

    enabled = bool(vals.get("enabled", os.getenv("HARNESS_TELEMETRY_ENABLED", "0") in ("1", "true", "TRUE")))
    metrics_enabled = bool(vals.get("metrics_enabled", os.getenv("HARNESS_METRICS_ENABLED", "0") in ("1", "true", "TRUE")))

    return TelemetryConfig(
        enabled=enabled,
        service_name=str(
            vals.get("service_name", "multi-model-harness")
        ),
        service_version=str(vals.get("service_version", "unknown")),
        otlp_endpoint=(
            str(vals["otlp_endpoint"])
            if vals.get("otlp_endpoint")
            else None
        ),
        metrics_enabled=metrics_enabled,
        traces_enabled=bool(vals.get("traces_enabled", False)),
        export_interval_seconds=float(
            vals.get("export_interval_seconds", 15.0)
        ),
    )

