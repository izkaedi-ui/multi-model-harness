"""Input validator — validates test case JSONL files against the canonical schema."""
from __future__ import annotations
import json
from pathlib import Path
from security_harness.errors import TestCaseError

REQUIRED_FIELDS = {"id", "version", "category", "subcategory", "messages", "expected"}

def validate_jsonl_file(path: Path) -> list[str]:
    """Validate a JSONL test case file. Returns list of error messages (empty = OK)."""
    errors: list[str] = []
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):

            line = line.strip()
            if not line or line.startswith("#"): continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{path.name}:{lineno}: JSON parse error: {exc}")
                continue
            for field in REQUIRED_FIELDS:
                if field not in record:
                    errors.append(f"{path.name}:{lineno}: missing field {field!r} in case {record.get('id', '?')!r}")
            if "messages" in record and not isinstance(record["messages"], list):
                errors.append(f"{path.name}:{lineno}: 'messages' must be a list")
    return errors
