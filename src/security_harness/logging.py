"""
Structured JSON logger with automatic redaction middleware.

Usage:
    from security_harness.logging import get_logger
    log = get_logger(__name__)
    log.info("Request dispatched", provider="openai", model="gpt-4o")
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

# Lazy import — redactor is initialised on first use to avoid circular imports
_redactor: Any = None


def _get_redactor() -> Any:
    global _redactor
    if _redactor is None:
        try:
            from security_harness.security.secret_redactor import SecretRedactor  # type: ignore[import]
            _redactor = SecretRedactor.default()
        except Exception:
            # Redactor not yet available (e.g. during bootstrap) — use no-op
            _redactor = None
    return _redactor


class _RedactingJsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON and redacts sensitive values."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Include any extra fields attached via log.info("msg", extra={...})
        skip = {
            "msg", "args", "created", "relativeCreated", "thread", "threadName",
            "process", "processName", "pathname", "filename", "module", "lineno",
            "funcName", "levelno", "levelname", "name", "exc_info", "exc_text",
            "stack_info", "msecs", "message",
        }
        for k, v in record.__dict__.items():
            if k not in skip:
                payload[k] = v

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        raw = json.dumps(payload, default=str)

        redactor = _get_redactor()
        if redactor is not None:
            raw = redactor.redact_string(raw)

        return raw


class _TextFormatter(logging.Formatter):
    """Human-readable formatter for local development."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        redactor = _get_redactor()
        if redactor is not None:
            base = redactor.redact_string(base)
        return base


def configure_logging(
    level: str = "INFO",
    fmt: str = "json",
) -> None:
    """
    Configure the root logger.

    Call once at application startup (e.g., in cli/main.py).

    Args:
        level: Log level name (DEBUG, INFO, WARNING, ERROR).
        fmt:   "json" (default) or "text" for human-readable output.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)

    if fmt == "json":
        handler.setFormatter(_RedactingJsonFormatter())
    else:
        handler.setFormatter(
            _TextFormatter(
                fmt="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric_level)

    # Suppress noisy third-party loggers
    for noisy in ("httpcore", "httpx", "openai._base_client", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger."""
    return logging.getLogger(name)


# Auto-configure from environment if HARNESS_LOG_LEVEL is set
_env_level = os.environ.get("HARNESS_LOG_LEVEL", "")
if _env_level:
    configure_logging(level=_env_level)
