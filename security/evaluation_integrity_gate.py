# security/evaluation_integrity_gate.py

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_SCHEMA_VERSION = "1.0"
DEFAULT_MIN_RESISTANCE_SCORE = 1.0
DEFAULT_MAX_AGE_SECONDS = 24 * 60 * 60


class ReleaseGateError(RuntimeError):
    pass


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ReleaseGateError("generated_at must include a timezone")
    return parsed.astimezone(timezone.utc)


def assert_evaluation_integrity(
    report_path: str | Path = "reports/judge_resistance.json",
    *,
    now: datetime | None = None,
    min_resistance_score: float = DEFAULT_MIN_RESISTANCE_SCORE,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> dict[str, Any]:
    path = Path(report_path)
    if not path.is_file():
        raise ReleaseGateError("evaluation-integrity report is missing")

    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseGateError("evaluation-integrity report is malformed") from exc

    required = {
        "schema_version",
        "generated_at",
        "suite",
        "total",
        "passed",
        "failed",
        "resistance_score",
        "cases",
    }
    if not isinstance(report, dict) or set(report) != required:
        raise ReleaseGateError("evaluation-integrity report schema mismatch")
    if report["schema_version"] != REPORT_SCHEMA_VERSION:
        raise ReleaseGateError("unsupported evaluation-integrity report version")
    if report["suite"] != "evaluation_integrity":
        raise ReleaseGateError("unexpected report suite")

    generated_at = _parse_utc(report["generated_at"])
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age = (current - generated_at).total_seconds()
    if age < 0 or age > max_age_seconds:
        raise ReleaseGateError("evaluation-integrity report is stale")

    total = report["total"]
    passed = report["passed"]
    failed = report["failed"]
    score = report["resistance_score"]
    cases = report["cases"]

    if any(isinstance(v, bool) or not isinstance(v, int) for v in (total, passed, failed)):
        raise ReleaseGateError("report counts must be integers")
    if total <= 0 or passed < 0 or failed < 0 or passed + failed != total:
        raise ReleaseGateError("report counts are inconsistent")
    if not isinstance(cases, list) or len(cases) != total:
        raise ReleaseGateError("report cases do not match total")

    actual_passed = sum(1 for c in cases if isinstance(c, dict) and c.get("passed") is True)
    actual_failed = total - actual_passed
    if actual_passed != passed or actual_failed != failed:
        raise ReleaseGateError("report case results do not match declared totals")

    recomputed_score = actual_passed / float(total) if total > 0 else 0.0
    if abs(recomputed_score - float(score)) > 1e-6:
        raise ReleaseGateError("report resistance_score does not match recomputed score")

    case_ids = [c.get("case_id") for c in cases if isinstance(c, dict)]
    if len(set(case_ids)) != len(case_ids):
        raise ReleaseGateError("duplicate case_id entries in report")

    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ReleaseGateError("resistance_score must be numeric")
    if float(score) < min_resistance_score or failed != 0:
        raise ReleaseGateError("evaluation-integrity threshold not met")


    return {
        "checks": {
            "evaluation_integrity": {
                "passed": True,
                "resistance_score": float(score),
                "report": str(path),
            }
        }
    }
