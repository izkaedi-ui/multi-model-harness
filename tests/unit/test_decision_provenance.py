# tests/unit/test_decision_provenance.py

"""
Unit tests for HMAC-Authenticated Chained Provenance Engine (Level 1-3 Prototype).
"""

from __future__ import annotations

import secrets
import pytest
from security.decision_provenance import (
    CANONICALIZATION_VERSION,
    SCHEMA_VERSION,
    DecisionProvenanceError,
    DecisionRecord,
    ProvenanceChain,
    assert_decision_provenance_gate,
    canonicalize_json_v1,
)


@pytest.fixture
def test_signing_key() -> bytes:
    return secrets.token_bytes(32)


def test_level1_canonicalization_consistency() -> None:
    dict1 = {"b": 2, "a": 1, "c": [3, 2]}
    dict2 = {"a": 1, "c": [3, 2], "b": 2}
    assert canonicalize_json_v1(dict1) == canonicalize_json_v1(dict2)
    assert canonicalize_json_v1(dict1) == b'{"a":1,"b":2,"c":[3,2]}'


def test_level1_digest_verification_success(test_signing_key: bytes) -> None:
    rec = DecisionRecord.create(
        decision_id="dec_001",
        correlation_id="corr_abc",
        tenant_id="tenant_a",
        user_id="user_1",
        resource_id="run_100",
        action="READ",
        verdict="ALLOW",
        signing_key=test_signing_key,
        timestamp="2026-07-24T12:00:00Z",
    )
    assert rec.verify_digest() is True
    assert rec.schema_version == SCHEMA_VERSION
    assert rec.canonicalization_version == CANONICALIZATION_VERSION


def test_level1_tampered_digest_rejected(test_signing_key: bytes) -> None:
    rec = DecisionRecord.create(
        decision_id="dec_001",
        correlation_id="corr_abc",
        tenant_id="tenant_a",
        user_id="user_1",
        resource_id="run_100",
        action="READ",
        verdict="DENY",
        signing_key=test_signing_key,
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
        verdict="ALLOW",  # Tampered!
        stream_sequence=rec.stream_sequence,
        previous_record_digest=rec.previous_record_digest,
        current_record_digest=rec.current_record_digest,
        signature=rec.signature,
    )
    with pytest.raises(DecisionProvenanceError):
        tampered.verify_digest()


def test_missing_or_short_signing_key_rejected() -> None:
    with pytest.raises(DecisionProvenanceError):
        DecisionRecord.create(
            decision_id="dec_001",
            correlation_id="corr_abc",
            tenant_id="tenant_a",
            user_id="user_1",
            resource_id="run_100",
            action="READ",
            verdict="ALLOW",
            signing_key=b"short-key",  # Under 32 bytes!
        )


def test_level2_signature_authenticity_and_wrong_key_rejection() -> None:
    key_a = secrets.token_bytes(32)
    key_b = secrets.token_bytes(32)
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


def test_level3_provenance_chain_validation_success(test_signing_key: bytes) -> None:
    rec1 = DecisionRecord.create(
        decision_id="d1", correlation_id="c1", tenant_id="t1", user_id="u1", resource_id="r1", action="READ", verdict="ALLOW", stream_sequence=1, previous_record_digest="GENESIS", signing_key=test_signing_key
    )
    rec2 = DecisionRecord.create(
        decision_id="d2", correlation_id="c2", tenant_id="t1", user_id="u1", resource_id="r1", action="UPDATE", verdict="ALLOW", stream_sequence=2, previous_record_digest=rec1.current_record_digest, signing_key=test_signing_key
    )
    assert ProvenanceChain.validate_chain([rec1, rec2], signing_key_or_public_key=test_signing_key) is True


def test_level3_broken_chain_link_rejected(test_signing_key: bytes) -> None:
    rec1 = DecisionRecord.create(
        decision_id="d1", correlation_id="c1", tenant_id="t1", user_id="u1", resource_id="r1", action="READ", verdict="ALLOW", stream_sequence=1, previous_record_digest="GENESIS", signing_key=test_signing_key
    )
    rec2 = DecisionRecord.create(
        decision_id="d2", correlation_id="c2", tenant_id="t1", user_id="u1", resource_id="r1", action="UPDATE", verdict="ALLOW", stream_sequence=2, previous_record_digest="TAMPERED_PREV_DIGEST", signing_key=test_signing_key
    )
    with pytest.raises(DecisionProvenanceError):
        ProvenanceChain.validate_chain([rec1, rec2], signing_key_or_public_key=test_signing_key)


def test_level3_sequence_break_rejected(test_signing_key: bytes) -> None:
    rec1 = DecisionRecord.create(
        decision_id="d1", correlation_id="c1", tenant_id="t1", user_id="u1", resource_id="r1", action="READ", verdict="ALLOW", stream_sequence=1, previous_record_digest="GENESIS", signing_key=test_signing_key
    )
    rec2 = DecisionRecord.create(
        decision_id="d2", correlation_id="c2", tenant_id="t1", user_id="u1", resource_id="r1", action="UPDATE", verdict="ALLOW", stream_sequence=3, previous_record_digest=rec1.current_record_digest, signing_key=test_signing_key
    )
    with pytest.raises(DecisionProvenanceError):
        ProvenanceChain.validate_chain([rec1, rec2], signing_key_or_public_key=test_signing_key)


def test_level3_duplicate_decision_id_rejected(test_signing_key: bytes) -> None:
    rec1 = DecisionRecord.create(
        decision_id="d1", correlation_id="c1", tenant_id="t1", user_id="u1", resource_id="r1", action="READ", verdict="ALLOW", stream_sequence=1, previous_record_digest="GENESIS", signing_key=test_signing_key
    )
    rec2 = DecisionRecord.create(
        decision_id="d1", correlation_id="c2", tenant_id="t1", user_id="u1", resource_id="r1", action="UPDATE", verdict="ALLOW", stream_sequence=2, previous_record_digest=rec1.current_record_digest, signing_key=test_signing_key
    )
    with pytest.raises(DecisionProvenanceError):
        ProvenanceChain.validate_chain([rec1, rec2], signing_key_or_public_key=test_signing_key)


def test_sensitive_secret_exclusion_enforced(test_signing_key: bytes) -> None:
    with pytest.raises(DecisionProvenanceError):
        DecisionRecord.create(
            decision_id="d1", correlation_id="c1", tenant_id="t1", user_id="u1", resource_id="sk-1234567890abcdefghijklmnopqrstuvwxyz", action="READ", verdict="ALLOW", signing_key=test_signing_key
        )


def test_decomposed_release_gate_assertions(test_signing_key: bytes) -> None:
    gate_res = assert_decision_provenance_gate(test_signing_key)
    assert gate_res["decision_schema_validation"] is True
    assert gate_res["decision_canonicalization"] is True
    assert gate_res["decision_digest_verification"] is True
    assert gate_res["decision_signature_verification"] is True
    assert gate_res["decision_chain_integrity"] is True
    assert gate_res["decision_sequence_validation"] is True
    assert gate_res["decision_duplicate_rejection"] is True
    assert gate_res["decision_sensitive_field_exclusion"] is True
