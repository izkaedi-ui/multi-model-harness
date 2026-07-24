# tests/unit/test_telemetry_config.py

import pytest

from telemetry.config import TelemetryConfig, load_telemetry_config


def test_telemetry_config_defaults() -> None:
    config = TelemetryConfig()
    assert not config.enabled
    assert config.service_name == "multi-model-harness"
    assert config.export_interval_seconds == 15.0


def test_telemetry_config_validation() -> None:
    with pytest.raises(ValueError, match="service_name must not be empty"):
        TelemetryConfig(service_name="")

    with pytest.raises(ValueError, match="export_interval_seconds must be greater than zero"):
        TelemetryConfig(export_interval_seconds=0)


def test_load_telemetry_config() -> None:
    cfg = load_telemetry_config({
        "enabled": True,
        "service_name": "custom-harness",
        "export_interval_seconds": 10.0,
    })
    assert cfg.enabled
    assert cfg.service_name == "custom-harness"
    assert cfg.export_interval_seconds == 10.0
