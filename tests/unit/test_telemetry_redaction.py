# tests/unit/test_telemetry_redaction.py

from telemetry.redaction import safe_attributes


def test_sensitive_attributes_are_removed() -> None:
    result = safe_attributes(
        {
            "provider": "openai",
            "api_key": "fake-secret",
            "authorization_header": "Bearer fake-secret",
            "prompt": "sensitive prompt",
            "model": "example-model",
        }
    )

    assert result == {
        "provider": "openai",
        "model": "example-model",
    }
