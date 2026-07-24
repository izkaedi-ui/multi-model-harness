# tests/unit/test_decision_provenance.py

"""
Unit tests for Decision Provenance engine.
"""

from __future__ import annotations

import pytest
from security.decision_provenance import DecisionRecord, DecisionProvenanceError


def test_decision_record_provenance_verification() -> None:
    rec = DecisionRecord.create(
        decision_id="dec_001",
        correlation_id="corr_abc",
        tenant_id="tenant_a",
        user_id="user_1",
        resource_id="run_100",
        action="READ",
        verdict="ALLOW",
        timestamp="2026-07-24T12:00:00Z",
    )
    assert rec.verify() is True
    assert len(rec.digest) == 64


def test_tampered_decision_record_rejected() -> None:
    rec = DecisionRecord.create(
        decision_id="dec_001",
        correlation_id="corr_abc",
        tenant_id="tenant_a",
        user_id="user_1",
        resource_id="run_100",
        action="READ",
        verdict="DENY",
        timestamp="2026-07-24T12:00:00Z",
    )
    # Tamper with object attribute
    tampered = DecisionRecord(
        decision_id=rec.decision_id,
        correlation_id=rec.correlation_id,
        timestamp=rec.timestamp,
        policy_version=rec.policy_version,
        evaluator_version=rec.evaluator_version,
        tenant_id=rec.tenant_id,
        user_id=rec.user_id,
        resource_id=rec.resource_id,
        action=rec.action,
        verdict="ALLOW", # Tampered!
        digest=rec.digest,
    )
    with pytest.raises(DecisionProvenanceError):
        tampered.verify()
