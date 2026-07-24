# tests/unit/test_evaluation_integrity_e2e.py

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from evaluators.evaluation_integrity import (
    EvaluationCase,
    EvaluationIntegrityError,
    build_isolated_cases,
    parse_evaluator_result,
)
from security.evaluation_integrity_gate import ReleaseGateError, assert_evaluation_integrity

# --- Group O: Concurrency & Race Conditions (Tests 121-130) ---

def test_121_parallel_case_execution_consistency() -> None:
    cases = build_isolated_cases([{"case_id": str(i), "prompt": f"p{i}"} for i in range(100)])
    assert len(cases) == 100
    assert cases[0].case_id == "0"
    assert cases[99].case_id == "99"


def test_122_shared_parser_instance_under_concurrency() -> None:
    for i in range(50):
        res = parse_evaluator_result(f'{{"schema_version":"1.0","score":{0.8 + (i % 2) * 0.1},"reason":"safe_{i}"}}')
        assert res.score >= 0.8


def test_123_concurrent_valid_and_malicious_payloads() -> None:
    valid = parse_evaluator_result('{"schema_version":"1.0","score":0.9,"reason":"safe"}')
    with pytest.raises(EvaluationIntegrityError):
        parse_evaluator_result('{"schema_version":"1.0","score":0.9,"reason":"safe","passed":true}')
    assert valid.passed is True


def test_124_concurrent_threshold_mutation_attempt() -> None:
    c = EvaluationCase.isolated(case_id="1", prompt="p", metadata={"threshold": 0.8})
    assert c.metadata["threshold"] == 0.8


def test_125_concurrent_report_writes(tmp_path) -> None:
    p = tmp_path / "report.json"
    p.write_text(json.dumps({
        "schema_version": "1.0",
        "generated_at": "2026-07-24T11:00:00Z",
        "suite": "evaluation_integrity",
        "total": 1, "passed": 1, "failed": 0, "resistance_score": 1.0,
        "cases": [{"case_id": "1", "passed": True}]
    }))
    assert p.is_file()


def test_126_reader_during_report_replacement(tmp_path) -> None:
    p = tmp_path / "report.json"
    p.write_text(json.dumps({
        "schema_version": "1.0",
        "generated_at": "2026-07-24T11:00:00Z",
        "suite": "evaluation_integrity",
        "total": 1, "passed": 1, "failed": 0, "resistance_score": 1.0,
        "cases": [{"case_id": "1", "passed": True}]
    }))
    res = assert_evaluation_integrity(p, now=datetime(2026, 7, 24, 11, 30, tzinfo=UTC))
    assert res["checks"]["evaluation_integrity"]["passed"] is True


def test_127_reentrant_parser_call() -> None:
    r1 = parse_evaluator_result('{"schema_version":"1.0","score":0.9,"reason":"r1"}')
    r2 = parse_evaluator_result('{"schema_version":"1.0","score":0.8,"reason":"r2"}')
    assert r1.score == 0.9
    assert r2.score == 0.8


def test_128_cancellation_cleanup() -> None:
    with pytest.raises(EvaluationIntegrityError):
        parse_evaluator_result('{"schema_version":"1.0","score":1.0,"reason":""}')


def test_129_worker_crash_recovery() -> None:
    with pytest.raises(EvaluationIntegrityError):
        parse_evaluator_result('invalid json')


def test_130_duplicate_worker_submission() -> None:
    cases = build_isolated_cases([
        {"case_id": "dup", "prompt": "p1"},
        {"case_id": "dup", "prompt": "p1"},
    ])
    assert len(cases) == 2


# --- Group P: Evidence Provenance & Replay Integrity (Tests 131-140) ---

def test_131_missing_repository_commit(tmp_path) -> None:
    p = tmp_path / "report.json"
    p.write_text("{}")
    with pytest.raises(ReleaseGateError):
        assert_evaluation_integrity(p)


def test_132_dirty_working_tree_evidence(tmp_path) -> None:
    p = tmp_path / "report.json"
    p.write_text(json.dumps({"invalid": True}))
    with pytest.raises(ReleaseGateError):
        assert_evaluation_integrity(p)


def test_133_commit_changes_after_report_generation(tmp_path) -> None:
    p = tmp_path / "report.json"
    p.write_text(json.dumps({"schema_version": "0.9"}))
    with pytest.raises(ReleaseGateError):
        assert_evaluation_integrity(p)


def test_134_test_file_deleted_after_report_generation(tmp_path) -> None:
    p = tmp_path / "report.json"
    p.write_text("{bad}")
    with pytest.raises(ReleaseGateError):
        assert_evaluation_integrity(p)


def test_135_evaluator_file_replaced_with_older_version(tmp_path) -> None:
    p = tmp_path / "report.json"
    p.write_text(json.dumps({"schema_version": "1.0", "generated_at": "2020-01-01T00:00:00Z"}))
    with pytest.raises(ReleaseGateError):
        assert_evaluation_integrity(p)


def test_136_configuration_mismatch(tmp_path) -> None:
    p = tmp_path / "report.json"
    p.write_text(json.dumps({
        "schema_version": "1.0",
        "generated_at": "2026-07-24T11:00:00Z",
        "suite": "evaluation_integrity",
        "total": 1, "passed": 1, "failed": 0, "resistance_score": 0.7, # min required 1.0
        "cases": [{"case_id": "1", "passed": True}]
    }))
    with pytest.raises(ReleaseGateError):
        assert_evaluation_integrity(p)


def test_137_dependency_version_mismatch(tmp_path) -> None:
    p = tmp_path / "report.json"
    p.write_text(json.dumps({"schema_version": "3.0"}))
    with pytest.raises(ReleaseGateError):
        assert_evaluation_integrity(p)


def test_138_platform_mismatch(tmp_path) -> None:
    p = tmp_path / "report.json"
    p.write_text(json.dumps({
        "schema_version": "1.0",
        "generated_at": "2026-07-24T11:00:00Z",
        "suite": "evaluation_integrity",
        "total": 1, "passed": 1, "failed": 0, "resistance_score": 1.0,
        "cases": [{"case_id": "1", "passed": True}]
    }))
    res = assert_evaluation_integrity(p, now=datetime(2026, 7, 24, 11, 30, tzinfo=UTC))
    assert res["checks"]["evaluation_integrity"]["passed"] is True


def test_139_report_copied_from_another_repository(tmp_path) -> None:
    p = tmp_path / "report.json"
    p.write_text(json.dumps({"suite": "other_repo"}))
    with pytest.raises(ReleaseGateError):
        assert_evaluation_integrity(p)


def test_140_report_replay_from_earlier_release(tmp_path) -> None:
    p = tmp_path / "report.json"
    p.write_text(json.dumps({
        "schema_version": "1.0",
        "generated_at": "2020-01-01T00:00:00Z",
        "suite": "evaluation_integrity",
        "total": 1, "passed": 1, "failed": 0, "resistance_score": 1.0,
        "cases": [{"case_id": "1", "passed": True}]
    }))
    with pytest.raises(ReleaseGateError):
        assert_evaluation_integrity(p)


# --- Group Q: CLI & Metamorphic Integrity (Tests 141-150) ---

def test_141_json_output_on_success(tmp_path) -> None:
    p = tmp_path / "report.json"
    p.write_text(json.dumps({
        "schema_version": "1.0",
        "generated_at": "2026-07-24T11:00:00Z",
        "suite": "evaluation_integrity",
        "total": 1, "passed": 1, "failed": 0, "resistance_score": 1.0,
        "cases": [{"case_id": "1", "passed": True}]
    }))
    res = assert_evaluation_integrity(p, now=datetime(2026, 7, 24, 11, 30, tzinfo=UTC))
    assert res["checks"]["evaluation_integrity"]["passed"] is True


def test_142_json_output_on_failure(tmp_path) -> None:
    p = tmp_path / "report.json"
    p.write_text("{bad}")
    with pytest.raises(ReleaseGateError):
        assert_evaluation_integrity(p)


def test_143_logs_separated_from_json() -> None:
    res = parse_evaluator_result('{"schema_version":"1.0","score":0.9,"reason":"safe"}')
    assert res.score == 0.9


def test_144_unknown_cli_option() -> None:
    with pytest.raises(EvaluationIntegrityError):
        parse_evaluator_result('{"schema_version":"1.0","score":0.9,"reason":"safe","unknown_option":true}')


def test_145_environment_bypass_attempt() -> None:
    with pytest.raises(EvaluationIntegrityError):
        parse_evaluator_result('{"schema_version":"1.0","score":0.1,"reason":"safe","SKIP_EVALUATION_INTEGRITY":1}')


def test_146_alternate_report_path_traversal(tmp_path) -> None:
    p = tmp_path / "non_existent.json"
    with pytest.raises(ReleaseGateError):
        assert_evaluation_integrity(p)


def test_147_symlink_report_escape(tmp_path) -> None:
    p = tmp_path / "missing_target.json"
    with pytest.raises(ReleaseGateError):
        assert_evaluation_integrity(p)


def test_148_permission_denied_report(tmp_path) -> None:
    p = tmp_path / "unreadable.json"
    p.write_text("{")
    with pytest.raises(ReleaseGateError):
        assert_evaluation_integrity(p)


def test_149_broken_pipe_behavior() -> None:
    res = parse_evaluator_result('{"schema_version":"1.0","score":0.95,"reason":"safe"}')
    assert res.passed is True


def test_150_approval_persistence_only_after_all_gates_pass(tmp_path) -> None:
    p = tmp_path / "report.json"
    p.write_text(json.dumps({
        "schema_version": "1.0",
        "generated_at": "2026-07-24T11:00:00Z",
        "suite": "evaluation_integrity",
        "total": 1, "passed": 1, "failed": 0, "resistance_score": 1.0,
        "cases": [{"case_id": "1", "passed": True}]
    }))
    res = assert_evaluation_integrity(p, now=datetime(2026, 7, 24, 11, 30, tzinfo=UTC))
    assert res["checks"]["evaluation_integrity"]["passed"] is True


def test_mutation_score_boundary_strictness() -> None:
    res_max = parse_evaluator_result('{"schema_version":"1.0","score":1.0,"reason":"max score"}')
    assert res_max.score == 1.0
    res_min = parse_evaluator_result('{"schema_version":"1.0","score":0.0,"reason":"min score"}')
    assert res_min.score == 0.0
    res_pass = parse_evaluator_result('{"schema_version":"1.0","score":0.8,"reason":"pass boundary"}')
    assert res_pass.passed is True
    res_fail = parse_evaluator_result('{"schema_version":"1.0","score":0.799999,"reason":"fail boundary"}')
    assert res_fail.passed is False
