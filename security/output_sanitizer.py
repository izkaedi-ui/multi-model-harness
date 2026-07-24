"""Output sanitizer — strips control characters and oversized payloads from model responses."""
from __future__ import annotations

import re
import unicodedata

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

def sanitize(text: str, max_chars: int = 64_000) -> str:
    text = unicodedata.normalize("NFC", text)
    text = _CONTROL.sub("", text)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[TRUNCATED]"
    return text
