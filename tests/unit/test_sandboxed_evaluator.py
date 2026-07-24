# tests/unit/test_sandboxed_evaluator.py

"""
Unit tests for Outer-Wall Evaluator Isolation Engine.
"""

from __future__ import annotations

import pytest
from runner.sandboxed_evaluator import (
    EvaluatorIsolationError,
    SandboxedEvaluatorRunner,
    assert_evaluator_outer_wall_isolation_gate,
    scrub_environment,
)


def test_environment_scrubbing() -> None:
    dirty = {
        "OPENAI_API_KEY": "sk-123456",
        "AWS_SECRET_ACCESS_KEY": "secret123",
        "DATABASE_URL": "postgres://user:pass@localhost/db",
        "NORMAL_VAR": "value",
    }
    clean = scrub_environment(dirty)
    assert "OPENAI_API_KEY" not in clean
    assert "AWS_SECRET_ACCESS_KEY" not in clean
    assert "DATABASE_URL" not in clean
    assert clean["NORMAL_VAR"] == "value"
    assert clean["HARNESS_EVALUATOR_SANDBOX"] == "true"


def test_sandboxed_evaluator_execution_success() -> None:
    runner = SandboxedEvaluatorRunner(timeout_sec=5.0)
    code = """
input_val = case_data.get("val", 0)
result = {
    "passed": input_val == 42,
    "score": 0.95,
    "details": {"computed": input_val * 2}
}
"""
    res = runner.run_evaluator_code(code, {"val": 42})
    assert res.passed is True
    assert res.score == 0.95
    assert res.details == {"computed": 84}


def test_sandboxed_evaluator_timeout_rejection() -> None:
    runner = SandboxedEvaluatorRunner(timeout_sec=1.0)
    code = """
import time
time.sleep(5.0)
result = {"passed": True, "score": 1.0}
"""
    with pytest.raises(EvaluatorIsolationError) as exc_info:
        runner.run_evaluator_code(code, {})
    assert "timed out" in str(exc_info.value).lower()


def test_sandboxed_evaluator_invalid_payload_rejection() -> None:
    runner = SandboxedEvaluatorRunner(timeout_sec=5.0)
    code = """
result = {"invalid": True}  # Missing passed and score
"""
    with pytest.raises(EvaluatorIsolationError):
        runner.run_evaluator_code(code, {})


def test_evaluator_gate_assertions() -> None:
    gate_res = assert_evaluator_outer_wall_isolation_gate()
    assert gate_res["evaluator_environment_scrubbing"] is True
    assert gate_res["evaluator_subprocess_isolation"] is True
    assert gate_res["evaluator_credential_leak_prevention"] is True
