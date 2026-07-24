"""
SHA-256 canonical fingerprint calculation for benchmark scenarios.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def calculate_fingerprint(data: dict[str, Any]) -> str:
    """Calculate deterministic SHA-256 fingerprint for scenario dictionary."""
    clean_data = {k: v for k, v in data.items() if k != "fingerprint"}
    canonical_json = json.dumps(clean_data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
