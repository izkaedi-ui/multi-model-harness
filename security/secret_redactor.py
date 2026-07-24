"""
Secret redactor — scrubs sensitive values from strings, dicts, and JSON.

Patterns are loaded from config/redaction.yaml. The redactor is applied:
  - Before any log write (via logging.py)
  - Before any report or artifact is written to disk
  - Before the dashboard fixture is exported

Usage:
    redactor = SecretRedactor.default()
    safe = redactor.redact_string(raw_text)
    safe_dict = redactor.redact_dict(response_payload)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import yaml


@dataclass
class _Pattern:
    regex: re.Pattern[str]
    replacement: str


class SecretRedactor:
    """Applies regex patterns and field-name rules to remove secrets."""

    def __init__(
        self,
        value_patterns: list[_Pattern],
        sensitive_field_names: set[str],
    ) -> None:
        self._patterns = value_patterns
        self._sensitive_fields = sensitive_field_names

    @classmethod
    def default(cls, config_path: str = "config/redaction.yaml") -> SecretRedactor:
        """Load patterns from redaction.yaml."""
        try:
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}
        except FileNotFoundError:
            return cls(value_patterns=[], sensitive_field_names=set())

        patterns: list[_Pattern] = []
        for entry in cfg.get("value_patterns", []):
            try:
                patterns.append(
                    _Pattern(
                        regex=re.compile(entry["pattern"]),
                        replacement=entry.get("replacement", "[REDACTED]"),
                    )
                )
            except re.error:
                pass

        sensitive = {
            name.lower()
            for name in cfg.get("sensitive_field_names", [])
        }

        return cls(value_patterns=patterns, sensitive_field_names=sensitive)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def redact_string(self, text: str) -> str:
        """Apply all value patterns to a raw string."""
        for pat in self._patterns:
            text = pat.regex.sub(pat.replacement, text)
        return text

    def redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Recursively redact a dictionary.

        - Keys matching sensitive_field_names have their values replaced.
        - String values are run through redact_string.
        - Nested dicts and lists are recursively processed.
        """
        return self._redact_value(data)  # type: ignore[return-value]

    def redact_json(self, json_str: str) -> str:
        """Parse JSON, redact, and re-serialise."""
        try:
            data = json.loads(json_str)
            redacted = self._redact_value(data)
            return json.dumps(redacted, default=str)
        except (json.JSONDecodeError, TypeError):
            # If it won't parse, just run the string patterns
            return self.redact_string(json_str)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _redact_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                k: "[REDACTED]" if k.lower() in self._sensitive_fields
                else self._redact_value(v)
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [self._redact_value(item) for item in value]
        if isinstance(value, str):
            return self.redact_string(value)
        return value

    def is_clean(self, text: str) -> bool:
        """Return True if no pattern matches the text (i.e., no secrets detected)."""
        for pat in self._patterns:
            if pat.regex.search(text):
                return False
        return True
