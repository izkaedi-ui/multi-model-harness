# tests/unit/test_provenance_store.py

"""
Unit tests for Atomic Append-Only ProvenanceStore.
"""

from __future__ import annotations

import os
import secrets
import tempfile
import pytest

from cryptography.hazmat.primitives.asymmetric import ed25519

from security.decision_provenance import DecisionProvenanceError, DecisionRecord
from security.provenance_store import ProvenanceStore


@pytest.fixture
def temp_db_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def test_hmac_key() -> bytes:
    return secrets.token_bytes(32)


def test_atomic_append_and_verification_success(temp_db_path: str, test_hmac_key: bytes) -> None:
    store = ProvenanceStore(db_path=temp_db_path)
    stream_id = "stream_100"

    rec1 = DecisionRecord.create(
        decision_id="dec_101",
        correlation_id="corr_101",
        tenant_id="t1",
        user_id="u1",
        resource_id="r1",
        action="READ",
        verdict="ALLOW",
        stream_sequence=1,
        previous_record_digest="GENESIS",
        signing_key=test_hmac_key,
    )
    assert store.append(stream_id, rec1, test_hmac_key) is True

    head = store.get_stream_head(stream_id)
    assert head == (1, rec1.current_record_digest)

    rec2 = DecisionRecord.create(
        decision_id="dec_102",
        correlation_id="corr_102",
        tenant_id="t1",
        user_id="u1",
        resource_id="r1",
        action="UPDATE",
        verdict="ALLOW",
        stream_sequence=2,
        previous_record_digest=rec1.current_record_digest,
        signing_key=test_hmac_key,
    )
    assert store.append(stream_id, rec2, test_hmac_key) is True

    assert store.verify_stored_stream(stream_id, test_hmac_key) is True


def test_ed25519_stream_append_and_public_key_verification(temp_db_path: str) -> None:
    store = ProvenanceStore(db_path=temp_db_path)
    stream_id = "ed_stream_200"

    ed_priv = ed25519.Ed25519PrivateKey.generate()
    ed_pub = ed_priv.public_key()

    rec1 = DecisionRecord.create_ed25519(
        decision_id="ed_dec_201",
        correlation_id="corr_201",
        tenant_id="t1",
        user_id="u1",
        resource_id="r1",
        action="READ",
        verdict="ALLOW",
        stream_sequence=1,
        previous_record_digest="GENESIS",
        private_key=ed_priv,
    )
    assert store.append(stream_id, rec1, ed_pub) is True

    rec2 = DecisionRecord.create_ed25519(
        decision_id="ed_dec_202",
        correlation_id="corr_202",
        tenant_id="t1",
        user_id="u1",
        resource_id="r1",
        action="DELETE",
        verdict="DENY",
        stream_sequence=2,
        previous_record_digest=rec1.current_record_digest,
        private_key=ed_priv,
    )
    assert store.append(stream_id, rec2, ed_pub) is True

    # Verifies stream using ONLY public key
    assert store.verify_stored_stream(stream_id, ed_pub) is True


def test_sequence_gap_rejection(temp_db_path: str, test_hmac_key: bytes) -> None:
    store = ProvenanceStore(db_path=temp_db_path)
    stream_id = "stream_gap"

    rec1 = DecisionRecord.create(
        decision_id="dec_gap_1",
        correlation_id="c1",
        tenant_id="t1",
        user_id="u1",
        resource_id="r1",
        action="READ",
        verdict="ALLOW",
        stream_sequence=1,
        previous_record_digest="GENESIS",
        signing_key=test_hmac_key,
    )
    store.append(stream_id, rec1, test_hmac_key)

    rec_gap = DecisionRecord.create(
        decision_id="dec_gap_3",
        correlation_id="c3",
        tenant_id="t1",
        user_id="u1",
        resource_id="r1",
        action="WRITE",
        verdict="DENY",
        stream_sequence=3,  # Sequence gap!
        previous_record_digest=rec1.current_record_digest,
        signing_key=test_hmac_key,
    )
    with pytest.raises(DecisionProvenanceError):
        store.append(stream_id, rec_gap, test_hmac_key)


def test_digest_link_break_rejection(temp_db_path: str, test_hmac_key: bytes) -> None:
    store = ProvenanceStore(db_path=temp_db_path)
    stream_id = "stream_link"

    rec1 = DecisionRecord.create(
        decision_id="dec_link_1",
        correlation_id="c1",
        tenant_id="t1",
        user_id="u1",
        resource_id="r1",
        action="READ",
        verdict="ALLOW",
        stream_sequence=1,
        previous_record_digest="GENESIS",
        signing_key=test_hmac_key,
    )
    store.append(stream_id, rec1, test_hmac_key)

    rec_broken_link = DecisionRecord.create(
        decision_id="dec_link_2",
        correlation_id="c2",
        tenant_id="t1",
        user_id="u1",
        resource_id="r1",
        action="WRITE",
        verdict="DENY",
        stream_sequence=2,
        previous_record_digest="BAD_DIGEST_LINK",
        signing_key=test_hmac_key,
    )
    with pytest.raises(DecisionProvenanceError):
        store.append(stream_id, rec_broken_link, test_hmac_key)


def test_duplicate_decision_id_rejection(temp_db_path: str, test_hmac_key: bytes) -> None:
    store = ProvenanceStore(db_path=temp_db_path)
    stream_id = "stream_dup"

    rec1 = DecisionRecord.create(
        decision_id="dec_dup_1",
        correlation_id="c1",
        tenant_id="t1",
        user_id="u1",
        resource_id="r1",
        action="READ",
        verdict="ALLOW",
        stream_sequence=1,
        previous_record_digest="GENESIS",
        signing_key=test_hmac_key,
    )
    store.append(stream_id, rec1, test_hmac_key)

    dup_rec = DecisionRecord.create(
        decision_id="dec_dup_1",  # Duplicate ID
        correlation_id="c2",
        tenant_id="t1",
        user_id="u1",
        resource_id="r1",
        action="WRITE",
        verdict="DENY",
        stream_sequence=2,
        previous_record_digest=rec1.current_record_digest,
        signing_key=test_hmac_key,
    )
    with pytest.raises(DecisionProvenanceError):
        store.append(stream_id, dup_rec, test_hmac_key)
