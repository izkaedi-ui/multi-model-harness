"""
Response normaliser — strips provider-specific envelope fields.

The adapters already return ModelResponse objects. This module provides
additional post-processing utilities: text trimming, control-character
removal, and oversized-response truncation.
"""

from __future__ import annotations

import re
import unicodedata


_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def normalise_text(text: str, max_chars: int = 64_000) -> str:
    """
    Clean and truncate a model response text.

    1. Normalise unicode to NFC.
    2. Remove control characters (except tab, newline, carriage return).
    3. Truncate to max_chars.

    Args:
        text:      Raw text from the model.
        max_chars: Maximum allowed length (characters).

    Returns:
        Cleaned, possibly truncated text.
    """
    # Normalise unicode
    text = unicodedata.normalize("NFC", text)
    # Remove control characters
    text = _CONTROL_CHARS.sub("", text)
    # Truncate
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[RESPONSE TRUNCATED]"
    return text


def extract_json_block(text: str) -> str | None:
    """
    Extract the first JSON block from a response that may contain markdown.

    Looks for ```json ... ``` fences first, then bare JSON objects/arrays.

    Returns:
        The extracted JSON string, or None if not found.
    """
    # Fenced code block
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    # Bare JSON object or array
    bare_match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if bare_match:
        return bare_match.group(1).strip()

    return None
