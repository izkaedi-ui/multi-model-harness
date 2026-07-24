"""
Exporter — writes fixture JSON for the standalone dashboard.

Output: artifacts/reports/fixture_<run_id>.json
"""

from __future__ import annotations

import json
import logging
import pathlib
from datetime import UTC, datetime
from typing import Any

from runner.metrics import RunMetrics
from security_harness.types import ModelResponse, Score, TestCase, Verdict

log = logging.getLogger(__name__)

_ARTIFACTS_DIR = pathlib.Path("artifacts/reports")


def export_fixture(
    run_id: str,
    results: list[tuple[TestCase, ModelResponse | Exception]],
    scores: list[Score],
    verdicts: list[Verdict],
    metrics: RunMetrics,
) -> str:
    """
    Write a self-contained JSON fixture for the HTML dashboard.

    Returns the absolute path to the fixture file.
    """
    _ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = _ARTIFACTS_DIR / f"fixture_{run_id}.json"

    # Build execution records
    executions = []
    for test_case, response_or_err in results:
        if isinstance(response_or_err, Exception):
            executions.append({
                "test_case_id": test_case.id,
                "category": test_case.category,
                "subcategory": test_case.subcategory,
                "status": "error",
                "error": str(response_or_err),
            })
        else:
            r = response_or_err
            executions.append({
                "test_case_id": test_case.id,
                "category": test_case.category,
                "subcategory": test_case.subcategory,
                "provider": r.provider,
                "model": r.model,
                "status": "completed",
                "finish_reason": r.finish_reason,
                "latency_ms": r.latency_ms,
                "input_tokens": r.usage.input_tokens,
                "output_tokens": r.usage.output_tokens,
                "text_preview": r.text[:500],
                "redaction_applied": r.redaction_applied,
            })

    fixture: dict[str, Any] = {
        "harness_version": "0.1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "metrics": metrics.to_dict(),
        "executions": executions,
        "scores": [
            {
                "execution_id": s.execution_id,
                "evaluator": s.evaluator_name,
                "metric": s.metric_name,
                "score": s.numeric_score,
                "passed": s.passed,
                "confidence": s.confidence,
                "explanation": s.explanation,
            }
            for s in scores
        ],
        "verdicts": [
            {
                "execution_id": v.execution_id,
                "status": v.status.value,
                "severity": v.severity.value,
                "confidence": v.confidence,
                "requires_human_review": v.requires_human_review,
                "blocking_metric": v.blocking_metric,
            }
            for v in verdicts
        ],
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(fixture, f, indent=2, default=str)

    # Write reproducibility manifest alongside fixture
    manifest_path = _ARTIFACTS_DIR / f"manifest_{run_id}.json"
    import platform
    manifest = {
        "run_id": run_id,
        "harness_version": "0.1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "total_executions": len(results),
        "total_cost_usd": metrics.total_cost_usd,
    }
    with manifest_path.open("w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2, default=str)

    log.info("exporter.fixture_written", extra={"path": str(output_path), "manifest": str(manifest_path)})
    return str(output_path.resolve())

