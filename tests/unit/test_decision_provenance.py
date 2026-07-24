# tests/unit/test_decision_provenance.py

"""
Unit tests for Level 1-4 Cryptographic Decision Provenance Engine.
"""

from __future__ import annotations

import pytest
from security.decision_provenance import (
    CANONICALIZATION_VERSION,
    DEFAULT_SIGNING_KEY,
    SCHEMA_VERSION,
    DecisionProvenanceError,
    DecisionRecord,
    ProvenanceChain,
    assert_decision_provenance_gate,
    rfc8785_canonicalize,
)


def test_level1_rfc8785_canonicalization_consistency() -> None:
    dict1 = {"b": 2, "a": 1, "c": [3, 2]}
    dict2 = {"a": 1, "c": [3, 2], "b": 2}
    assert rfc8785_canonicalize(dict1) == rfc8785_canonicalize(dict2)
    assert rfc8785_canonicalize(dict1) == b'{"a":1,"b":2,"c":[3,2]}'


def test_level1_digest_verification_success() -> None:
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
    assert rec.verify_digest() is True
    assert rec.schema_version == SCHEMA_VERSION
    assert rec.canonicalization_version == CANONICALIZATION_VERSION


def test_level1_tampered_digest_rejected() -> None:
    rec = DecisionRecord.create(
        decision_id="dec_001",
        correlation_id="corr_abc",
        tenant_id="tenant_a",
        user_id="user_1",
        resource_id="run_100",
        action="READ",
        verdict="DENY",
    )
    tampered = DecisionRecord(
        decision_id=rec.decision_id,
        correlation_id=rec.correlation_id,
        timestamp=rec.timestamp,
        schema_version=rec.schema_version,
        canonicalization_version=rec.canonicalization_version,
        policy_version=rec.policy_version,
        evaluator_version=rec.evaluator_version,
        tenant_id=rec.tenant_id,
        user_id=rec.user_id,
        resource_id=rec.resource_id,
        action=rec.action,
        verdict="ALLOW", # Tampered!
        stream_sequence=rec.stream_sequence,
        previous_record_digest=rec.previous_record_digest,
        current_record_digest=rec.current_record_digest,
        signature=rec.signature,
    )
    with pytest.raises(DecisionProvenanceError):
        tampered.verify_digest()


def test_level2_signature_authenticity_and_wrong_key_rejection() -> None:
    key_a = b"signing-key-a"
    key_b = b"signing-key-b"
    rec = DecisionRecord.create(
        decision_id="dec_001",
        correlation_id="corr_abc",
        tenant_id="tenant_a",
        user_id="user_1",
        resource_id="run_100",
        action="READ",
        verdict="ALLOW",
        signing_key=key_a,
    )
    assert rec.verify_signature(key_a) is True

    with pytest.raises(DecisionProvenanceError):
        rec.verify_signature(key_b)


def test_level3_provenance_chain_validation_success() -> None:
    rec1 = DecisionRecord.create(
        decision_id="d1", correlation_id="c1", tenant_id="t1", user_id="u1", resource_id="r1", action="READ", verdict="ALLOW", stream_sequence=1, previous_record_digest="GENESIS"
    )
    rec2 = DecisionRecord.create(
        decision_id="d2", correlation_id="c2", tenant_id="t1", user_id="u1", resource_id="r1", action="UPDATE", verdict="ALLOW", stream_sequence=2, previous_record_digest=rec1.current_record_digest
    )
    assert ProvenanceChain.validate_chain([rec1, rec2]) is True


def test_level3_broken_chain_link_rejected() -> None:
    rec1 = DecisionRecord.create(
        decision_id="d1", correlation_id="c1", tenant_id="t1", user_id="u1", resource_id="r1", action="READ", verdict="ALLOW", stream_sequence=1, previous_record_digest="GENESIS"
    )
    rec2 = DecisionRecord.create(
        decision_id="d2", correlation_id="c2", tenant_id="t1", user_id="u1", resource_id="r1", action="UPDATE", verdict="ALLOW", stream_sequence=2, previous_record_digest="TAMPERED_PREV_DIGEST"
    )
    with pytest.raises(DecisionProvenanceError):
        ProvenanceChain.validate_chain([rec1, rec2])


def test_level3_sequence_break_rejected() -> None:
    rec1 = DecisionRecord.create(
        decision_id="d1", correlation_id="c1", tenant_id="t1", user_id="u1", resource_id="r1", action="READ", verdict="ALLOW", stream_sequence=1, previous_record_digest="GENESIS"
    )
    rec2 = DecisionRecord.create(
        decision_id="d2", correlation_id="c2", tenant_id="t1", user_id="u1", resource_id="r1", action="UPDATE", verdict="ALLOW", stream_sequence=3, previous_record_digest=rec1.current_record_digest
    )
    with pytest.raises(DecisionProvenanceError):
        ProvenanceChain.validate_chain([rec1, rec2])


def test_level3_duplicate_decision_id_rejected() -> None:
    rec1 = DecisionRecord.create(
        decision_id="d1", correlation_id="c1", tenant_id="t1", user_id="u1", resource_id="r1", action="READ", verdict="ALLOW", stream_sequence=1, previous_record_digest="GENESIS"
    )
    rec2 = DecisionRecord.create(
        decision_id="d1", correlation_id="c2", tenant_id="t1", user_id="u1", resource_id="r1", action="UPDATE", verdict="ALLOW", stream_sequence=2, previous_record_digest=rec1.current_record_digest
    )
    with pytest.raises(DecisionProvenanceError):
        ProvenanceChain.validate_chain([rec1, rec2])


def test_sensitive_secret_exclusion_enforced() -> None:
    with pytest.raises(DecisionProvenanceError):
        DecisionRecord.create(
            decision_id="d1", correlation_id="c1", tenant_id="t1", user_id="u1", resource_id="sk-1234567890abcdefghijklmnopqrstuvwxyz", action="READ", verdict="ALLOW"
        )


def test_decomposed_release_gate_assertions() -> None:
    gate_res = assert_decision_provenance_gate()
    assert gate_res["decision_schema_validation"] is True
    assert gate_res["decision_canonicalization"] is True
    assert gate_res["decision_digest_verification"] is True
    assert gate_res["decision_signature_verification"] is True
    assert gate_res["decision_chain_integrity"] is True
    assert gate_res["decision_sequence_validation"] is True
    assert gate_res["decision_duplicate_rejection"] is True
    assert gate_res["decision_sensitive_field_exclusion"] is True
