# telemetry/redaction.py

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

FORBIDDEN_ATTRIBUTE_NAMES = frozenset(
    {
        "api_key",
        "authorization",
        "access_token",
        "refresh_token",
        "secret",
        "password",
        "prompt",
        "response",
        "raw_response",
        "thought_signature",
    }
)


def safe_attributes(
    attributes: Mapping[str, Any],
) -> dict[str, str | int | float | bool]:
    safe: dict[str, str | int | float | bool] = {}

    for key, value in attributes.items():
        normalized = key.casefold()

        if any(
            forbidden in normalized
            for forbidden in FORBIDDEN_ATTRIBUTE_NAMES
        ):
            continue

        if isinstance(value, (str, int, float, bool)):
            safe[key] = value
        elif value is not None:
            safe[key] = str(value)[:256]

    return safe
