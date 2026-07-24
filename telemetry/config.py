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
    values: Mapping[str, object] | None,
) -> TelemetryConfig:
    if not values:
        return TelemetryConfig()

    return TelemetryConfig(
        enabled=bool(values.get("enabled", False)),
        service_name=str(
            values.get("service_name", "multi-model-harness")
        ),
        service_version=str(values.get("service_version", "unknown")),
        otlp_endpoint=(
            str(values["otlp_endpoint"])
            if values.get("otlp_endpoint")
            else None
        ),
        metrics_enabled=bool(values.get("metrics_enabled", False)),
        traces_enabled=bool(values.get("traces_enabled", False)),
        export_interval_seconds=float(
            values.get("export_interval_seconds", 15.0)
        ),
    )
