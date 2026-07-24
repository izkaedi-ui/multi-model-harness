# security/decision_provenance.py

"""
Decision Provenance Engine — Level 1-4 Cryptographic Audit Chain.

Formalizes the invariant:
  "Every decision that crosses a trust boundary should be deterministic, least-privileged,
   auditable, and backed by verifiable evidence."

Security Architecture:
  Level 1 — Canonical Payload Integrity (HARNESS-JSON-SORTED-COMPACT-v1 + SHA-256)
  Level 2 — Authenticity (Ed25519 Asymmetric Digital Signatures & HMAC-SHA256 Fallback)
  Level 3 — Historical Chaining (previous_record_digest + stream_sequence link)
  Level 4 — Transparency Log & Immutable Append-Only Store
"""

from __future__ import annotations

import hmac
import hashlib
import json
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Sequence

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

SCHEMA_VERSION = "1.0.0"
CANONICALIZATION_VERSION = "HARNESS-JSON-SORTED-COMPACT-v1"

SECRET_PATTERN = re.compile(r"(sk-[a-zA-Z0-9]{20,}|Bearer\s+[a-zA-Z0-9_\-\.]+|api-key\s*:\s*[a-zA-Z0-9_\-]+)", re.IGNORECASE)


class DecisionProvenanceError(ValueError):
    """Raised when a decision record or chain fails provenance, signature, or tamper verification."""


def canonicalize_json_v1(payload: dict[str, Any]) -> bytes:
    """Produces deterministic compact JSON bytes (sorted keys, compact separators, UTF-8)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sanitize_value(val: Any) -> Any:
    if isinstance(val, str):
        if SECRET_PATTERN.search(val):
            raise DecisionProvenanceError("Sensitive secret detected in decision record payload")
        return val
    elif isinstance(val, dict):
        return {k: _sanitize_value(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [_sanitize_value(v) for v in val]
    return val


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    decision_id: str
    correlation_id: str
    timestamp: str
    schema_version: str
    canonicalization_version: str
    policy_version: str
    evaluator_version: str
    tenant_id: str
    user_id: str
    resource_id: str
    action: str
    verdict: str
    stream_sequence: int
    previous_record_digest: str
    current_record_digest: str
    signature: str
    signing_key_id: str = "key_hmac_v1"
    algorithm: str = "HMAC-SHA256"

    @classmethod
    def create(
        cls,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        user_id: str,
        resource_id: str,
        action: str,
        verdict: str,
        signing_key: bytes,
        signing_key_id: str = "key_hmac_v1",
        stream_sequence: int = 1,
        previous_record_digest: str = "GENESIS",
        policy_version: str = "1.0.0",
        evaluator_version: str = "1.0.0",
        timestamp: str | None = None,
    ) -> DecisionRecord:
        if not signing_key or len(signing_key) < 32:
            raise DecisionProvenanceError("signing_key must contain at least 256 bits (32 bytes)")
        if stream_sequence <= 0:
            raise DecisionProvenanceError("stream_sequence must be a positive integer")

        ts = timestamp or datetime.now(UTC).isoformat().replace("+00:00", "Z")
        raw_payload = {
            "action": action,
            "algorithm": "HMAC-SHA256",
            "canonicalization_version": CANONICALIZATION_VERSION,
            "correlation_id": correlation_id,
            "decision_id": decision_id,
            "evaluator_version": evaluator_version,
            "policy_version": policy_version,
            "previous_record_digest": previous_record_digest,
            "resource_id": resource_id,
            "schema_version": SCHEMA_VERSION,
            "signing_key_id": signing_key_id,
            "stream_sequence": stream_sequence,
            "tenant_id": tenant_id,
            "timestamp": ts,
            "user_id": user_id,
            "verdict": verdict,
        }

        sanitized_payload = _sanitize_value(raw_payload)
        canonical_bytes = canonicalize_json_v1(sanitized_payload)
        current_digest = hashlib.sha256(canonical_bytes).hexdigest()

        sig = hmac.new(signing_key, current_digest.encode("utf-8"), hashlib.sha256).hexdigest()

        return cls(
            decision_id=decision_id,
            correlation_id=correlation_id,
            timestamp=ts,
            schema_version=SCHEMA_VERSION,
            canonicalization_version=CANONICALIZATION_VERSION,
            policy_version=policy_version,
            evaluator_version=evaluator_version,
            tenant_id=tenant_id,
            user_id=user_id,
            resource_id=resource_id,
            action=action,
            verdict=verdict,
            stream_sequence=stream_sequence,
            previous_record_digest=previous_record_digest,
            current_record_digest=current_digest,
            signature=sig,
            signing_key_id=signing_key_id,
            algorithm="HMAC-SHA256",
        )

    @classmethod
    def create_ed25519(
        cls,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        user_id: str,
        resource_id: str,
        action: str,
        verdict: str,
        private_key: ed25519.Ed25519PrivateKey,
        signing_key_id: str = "key_ed25519_v1",
        stream_sequence: int = 1,
        previous_record_digest: str = "GENESIS",
        policy_version: str = "1.0.0",
        evaluator_version: str = "1.0.0",
        timestamp: str | None = None,
    ) -> DecisionRecord:
        if not isinstance(private_key, ed25519.Ed25519PrivateKey):
            raise DecisionProvenanceError("private_key must be an instance of Ed25519PrivateKey")
        if stream_sequence <= 0:
            raise DecisionProvenanceError("stream_sequence must be a positive integer")

        ts = timestamp or datetime.now(UTC).isoformat().replace("+00:00", "Z")
        raw_payload = {
            "action": action,
            "algorithm": "Ed25519",
            "canonicalization_version": CANONICALIZATION_VERSION,
            "correlation_id": correlation_id,
            "decision_id": decision_id,
            "evaluator_version": evaluator_version,
            "policy_version": policy_version,
            "previous_record_digest": previous_record_digest,
            "resource_id": resource_id,
            "schema_version": SCHEMA_VERSION,
            "signing_key_id": signing_key_id,
            "stream_sequence": stream_sequence,
            "tenant_id": tenant_id,
            "timestamp": ts,
            "user_id": user_id,
            "verdict": verdict,
        }

        sanitized_payload = _sanitize_value(raw_payload)
        canonical_bytes = canonicalize_json_v1(sanitized_payload)
        current_digest = hashlib.sha256(canonical_bytes).hexdigest()

        # Sign digest using Ed25519 Private Key
        sig_bytes = private_key.sign(current_digest.encode("utf-8"))
        sig_hex = sig_bytes.hex()

        return cls(
            decision_id=decision_id,
            correlation_id=correlation_id,
            timestamp=ts,
            schema_version=SCHEMA_VERSION,
            canonicalization_version=CANONICALIZATION_VERSION,
            policy_version=policy_version,
            evaluator_version=evaluator_version,
            tenant_id=tenant_id,
            user_id=user_id,
            resource_id=resource_id,
            action=action,
            verdict=verdict,
            stream_sequence=stream_sequence,
            previous_record_digest=previous_record_digest,
            current_record_digest=current_digest,
            signature=sig_hex,
            signing_key_id=signing_key_id,
            algorithm="Ed25519",
        )

    def _build_canonical_payload(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "algorithm": self.algorithm,
            "canonicalization_version": self.canonicalization_version,
            "correlation_id": self.correlation_id,
            "decision_id": self.decision_id,
            "evaluator_version": self.evaluator_version,
            "policy_version": self.policy_version,
            "previous_record_digest": self.previous_record_digest,
            "resource_id": self.resource_id,
            "schema_version": self.schema_version,
            "signing_key_id": self.signing_key_id,
            "stream_sequence": self.stream_sequence,
            "tenant_id": self.tenant_id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "verdict": self.verdict,
        }

    def verify_digest(self) -> bool:
        """Level 1 verification: Re-computes and verifies the canonical digest."""
        if self.schema_version != SCHEMA_VERSION:
            raise DecisionProvenanceError(f"Unsupported schema_version: {self.schema_version}")
        if self.canonicalization_version != CANONICALIZATION_VERSION:
            raise DecisionProvenanceError(f"Unsupported canonicalization_version: {self.canonicalization_version}")

        payload = self._build_canonical_payload()
        _sanitize_value(payload)
        expected_digest = hashlib.sha256(canonicalize_json_v1(payload)).hexdigest()
        if self.current_record_digest != expected_digest:
            raise DecisionProvenanceError("Decision record digest mismatch (tampering detected)")
        return True

    def verify_signature(
        self,
        signing_key_or_public_key: bytes | ed25519.Ed25519PublicKey,
    ) -> bool:
        """
        Level 2 verification:
          - HMAC-SHA256: verifies with symmetric secret bytes
          - Ed25519: verifies using ONLY public key bytes / Ed25519PublicKey (asymmetric non-repudiation)
        """
        self.verify_digest()

        if self.algorithm == "HMAC-SHA256":
            if not isinstance(signing_key_or_public_key, bytes) or len(signing_key_or_public_key) < 32:
                raise DecisionProvenanceError("HMAC verification requires symmetric signing key bytes >= 32 bytes")
            expected_sig = hmac.new(signing_key_or_public_key, self.current_record_digest.encode("utf-8"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(self.signature, expected_sig):
                raise DecisionProvenanceError("Decision record HMAC signature mismatch (unauthorized signer)")
            return True

        elif self.algorithm == "Ed25519":
            if isinstance(signing_key_or_public_key, bytes):
                try:
                    pub_key = ed25519.Ed25519PublicKey.from_public_bytes(signing_key_or_public_key)
                except Exception as e:
                    raise DecisionProvenanceError(f"Invalid Ed25519 public key bytes: {e}")
            elif isinstance(signing_key_or_public_key, ed25519.Ed25519PublicKey):
                pub_key = signing_key_or_public_key
            else:
                raise DecisionProvenanceError("Ed25519 verification requires Ed25519PublicKey or 32-byte raw public key")

            try:
                sig_bytes = bytes.fromhex(self.signature)
                pub_key.verify(sig_bytes, self.current_record_digest.encode("utf-8"))
                return True
            except Exception as e:
                raise DecisionProvenanceError(f"Decision record Ed25519 signature mismatch (unauthorized signer): {e}")

        else:
            raise DecisionProvenanceError(f"Unsupported signature algorithm: {self.algorithm}")


class ProvenanceChain:
    """Level 3 Verification Engine: Validates sequential audit chains."""

    @staticmethod
    def validate_chain(
        records: Sequence[DecisionRecord],
        *,
        signing_key_or_public_key: bytes | ed25519.Ed25519PublicKey,
    ) -> bool:
        if not records:
            raise DecisionProvenanceError("Provenance chain is empty")

        seen_decision_ids: set[str] = set()
        expected_prev_digest = "GENESIS"
        expected_seq = 1

        for i, rec in enumerate(records):
            # 1. Level 1 & 2 Verification per record
            rec.verify_signature(signing_key_or_public_key)

            # 2. Duplicate decision ID check
            if rec.decision_id in seen_decision_ids:
                raise DecisionProvenanceError(f"Duplicate decision_id detected in chain: {rec.decision_id}")
            seen_decision_ids.add(rec.decision_id)

            # 3. Monotonic sequence check
            if rec.stream_sequence != expected_seq:
                raise DecisionProvenanceError(f"Sequence break at index {i}: expected {expected_seq}, got {rec.stream_sequence}")

            # 4. Chain link digest match
            if i == 0 and rec.previous_record_digest != "GENESIS":
                raise DecisionProvenanceError("First record in chain must have previous_record_digest='GENESIS'")
            if i > 0 and rec.previous_record_digest != expected_prev_digest:
                raise DecisionProvenanceError(f"Chain broken at index {i}: previous_record_digest mismatch")

            expected_prev_digest = rec.current_record_digest
            expected_seq += 1

        return True


def assert_decision_provenance_gate(signing_key: bytes | None = None) -> dict[str, bool]:
    """Decomposed Release Gate Verification Function with Real Executable Negative Tests."""
    hmac_key = signing_key or secrets.token_bytes(32)

    # 1. HMAC Verification Path
    rec1 = DecisionRecord.create(
        decision_id="dec_001",
        correlation_id="corr_100",
        tenant_id="tenant_a",
        user_id="user_1",
        resource_id="run_1",
        action="READ",
        verdict="ALLOW",
        stream_sequence=1,
        previous_record_digest="GENESIS",
        signing_key=hmac_key,
    )
    rec2 = DecisionRecord.create(
        decision_id="dec_002",
        correlation_id="corr_101",
        tenant_id="tenant_a",
        user_id="user_1",
        resource_id="run_1",
        action="DELETE",
        verdict="DENY",
        stream_sequence=2,
        previous_record_digest=rec1.current_record_digest,
        signing_key=hmac_key,
    )

    valid_chain = ProvenanceChain.validate_chain([rec1, rec2], signing_key_or_public_key=hmac_key)

    # 2. Ed25519 Asymmetric Verification Path & Negative Check
    ed_priv = ed25519.Ed25519PrivateKey.generate()
    ed_pub = ed_priv.public_key()
    ed_wrong_pub = ed25519.Ed25519PrivateKey.generate().public_key()

    ed_rec1 = DecisionRecord.create_ed25519(
        decision_id="ed_dec_001",
        correlation_id="corr_200",
        tenant_id="tenant_a",
        user_id="user_1",
        resource_id="run_1",
        action="READ",
        verdict="ALLOW",
        stream_sequence=1,
        previous_record_digest="GENESIS",
        private_key=ed_priv,
    )
    ed_sig_ok = ed_rec1.verify_signature(ed_pub)

    ed_wrong_key_rejection = False
    try:
        ed_rec1.verify_signature(ed_wrong_pub)
    except DecisionProvenanceError:
        ed_wrong_key_rejection = True

    ed25519_gate_ok = ed_sig_ok and ed_wrong_key_rejection

    # 3. ProvenanceStore Atomic Append-Only Persistence Verification
    try:
        from security.provenance_store import ProvenanceStore
        store = ProvenanceStore(db_path=":memory:")
        store.append("gate_stream", ed_rec1, ed_pub)
        store_ok = store.verify_stored_stream("gate_stream", ed_pub)
    except Exception:
        store_ok = False

    # 4. Executable Negative Check: Duplicate Rejection
    duplicate_rejection = False
    try:
        dup_rec = DecisionRecord.create(
            decision_id="dec_001",
            correlation_id="corr_102",
            tenant_id="tenant_a",
            user_id="user_1",
            resource_id="run_1",
            action="WRITE",
            verdict="DENY",
            stream_sequence=3,
            previous_record_digest=rec2.current_record_digest,
            signing_key=hmac_key,
        )
        ProvenanceChain.validate_chain([rec1, rec2, dup_rec], signing_key_or_public_key=hmac_key)
    except DecisionProvenanceError:
        duplicate_rejection = True

    # 5. Executable Negative Check: Sensitive Secret Exclusion
    sensitive_exclusion = False
    try:
        DecisionRecord.create(
            decision_id="dec_secret",
            correlation_id="corr_secret",
            tenant_id="tenant_a",
            user_id="user_1",
            resource_id="Bearer seeded-test-secret-token",
            action="READ",
            verdict="DENY",
            signing_key=hmac_key,
        )
    except DecisionProvenanceError:
        sensitive_exclusion = True

    # 6. Executable Negative Check: Sequence Gap Validation
    sequence_validation = False
    try:
        gap_rec = DecisionRecord.create(
            decision_id="dec_003",
            correlation_id="corr_103",
            tenant_id="tenant_a",
            user_id="user_1",
            resource_id="run_1",
            action="WRITE",
            verdict="DENY",
            stream_sequence=5,
            previous_record_digest=rec2.current_record_digest,
            signing_key=hmac_key,
        )
        ProvenanceChain.validate_chain([rec1, rec2, gap_rec], signing_key_or_public_key=hmac_key)
    except DecisionProvenanceError:
        sequence_validation = True

    # 7. Executable Negative Check: Wrong Signature Key Rejection
    wrong_key_rejection = False
    try:
        rec1.verify_signature(secrets.token_bytes(32))
    except DecisionProvenanceError:
        wrong_key_rejection = True

    return {
        "decision_schema_validation": rec1.schema_version == SCHEMA_VERSION,
        "decision_canonicalization": rec1.canonicalization_version == CANONICALIZATION_VERSION,
        "decision_digest_verification": rec1.verify_digest(),
        "decision_signature_verification": wrong_key_rejection,
        "decision_ed25519_verification": ed25519_gate_ok,
        "decision_append_only_persistence": store_ok,
        "decision_chain_integrity": valid_chain,
        "decision_sequence_validation": sequence_validation,
        "decision_duplicate_rejection": duplicate_rejection,
        "decision_sensitive_field_exclusion": sensitive_exclusion,
    }
