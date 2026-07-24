# security/decision_provenance.py

"""
Decision Provenance Engine — HMAC-Authenticated Chained Provenance Prototype (Level 1-3).

Formalizes the invariant:
  "Every decision that crosses a trust boundary should be deterministic, least-privileged,
   auditable, and backed by verifiable evidence."

Security Architecture:
  Level 1 — Canonical Payload Integrity (HARNESS-JSON-SORTED-COMPACT-v1 + SHA-256)
  Level 2 — Authenticity (Cryptographic HMAC-SHA256 verification with injected signing keys)
  Level 3 — Historical Chaining (previous_record_digest + stream_sequence link)
  (Level 4 Transparency log & Ed25519 public key verification pending external anchoring)
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
            "canonicalization_version": CANONICALIZATION_VERSION,
            "correlation_id": correlation_id,
            "decision_id": decision_id,
            "evaluator_version": evaluator_version,
            "policy_version": policy_version,
            "previous_record_digest": previous_record_digest,
            "resource_id": resource_id,
            "schema_version": SCHEMA_VERSION,
            "stream_sequence": stream_sequence,
            "tenant_id": tenant_id,
            "timestamp": ts,
            "user_id": user_id,
            "verdict": verdict,
        }

        # 1. Redaction & Sanitization Check
        sanitized_payload = _sanitize_value(raw_payload)

        # 2. Level 1 Canonical Digest Computation
        canonical_bytes = canonicalize_json_v1(sanitized_payload)
        current_digest = hashlib.sha256(canonical_bytes).hexdigest()

        # 3. Level 2 Cryptographic HMAC Signature Generation
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
        )

    def _build_canonical_payload(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "canonicalization_version": self.canonicalization_version,
            "correlation_id": self.correlation_id,
            "decision_id": self.decision_id,
            "evaluator_version": self.evaluator_version,
            "policy_version": self.policy_version,
            "previous_record_digest": self.previous_record_digest,
            "resource_id": self.resource_id,
            "schema_version": self.schema_version,
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

    def verify_signature(self, signing_key: bytes) -> bool:
        """Level 2 verification: Verifies the cryptographic HMAC signature against an injected signing key."""
        if not signing_key or len(signing_key) < 32:
            raise DecisionProvenanceError("signing_key must contain at least 256 bits (32 bytes)")
        self.verify_digest()
        expected_sig = hmac.new(signing_key, self.current_record_digest.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(self.signature, expected_sig):
            raise DecisionProvenanceError("Decision record signature mismatch (unauthorized signer)")
        return True


class ProvenanceChain:
    """Level 3 Verification Engine: Validates sequential audit chains."""

    @staticmethod
    def validate_chain(
        records: Sequence[DecisionRecord],
        *,
        signing_key: bytes,
    ) -> bool:
        if not signing_key or len(signing_key) < 32:
            raise DecisionProvenanceError("signing_key must contain at least 256 bits (32 bytes)")
        if not records:
            raise DecisionProvenanceError("Provenance chain is empty")

        seen_decision_ids: set[str] = set()
        expected_prev_digest = "GENESIS"
        expected_seq = 1

        for i, rec in enumerate(records):
            # 1. Level 1 & 2 Verification per record
            rec.verify_signature(signing_key)

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
    key = signing_key or secrets.token_bytes(32)

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
        signing_key=key,
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
        signing_key=key,
    )

    # 1. Positive Chain Verification
    valid_chain = ProvenanceChain.validate_chain([rec1, rec2], signing_key=key)

    # 2. Executable Negative Check: Duplicate Rejection
    duplicate_rejection = False
    try:
        dup_rec = DecisionRecord.create(
            decision_id="dec_001",  # Duplicate ID
            correlation_id="corr_102",
            tenant_id="tenant_a",
            user_id="user_1",
            resource_id="run_1",
            action="WRITE",
            verdict="DENY",
            stream_sequence=3,
            previous_record_digest=rec2.current_record_digest,
            signing_key=key,
        )
        ProvenanceChain.validate_chain([rec1, rec2, dup_rec], signing_key=key)
    except DecisionProvenanceError:
        duplicate_rejection = True

    # 3. Executable Negative Check: Sensitive Secret Exclusion
    sensitive_exclusion = False
    try:
        DecisionRecord.create(
            decision_id="dec_secret",
            correlation_id="corr_secret",
            tenant_id="tenant_a",
            user_id="user_1",
            resource_id="Bearer seeded-test-secret-token",  # Sensitive!
            action="READ",
            verdict="DENY",
            signing_key=key,
        )
    except DecisionProvenanceError:
        sensitive_exclusion = True

    # 4. Executable Negative Check: Sequence Gap Validation
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
            stream_sequence=5,  # Sequence gap!
            previous_record_digest=rec2.current_record_digest,
            signing_key=key,
        )
        ProvenanceChain.validate_chain([rec1, rec2, gap_rec], signing_key=key)
    except DecisionProvenanceError:
        sequence_validation = True

    # 5. Executable Negative Check: Wrong Signature Key Rejection
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
        "decision_chain_integrity": valid_chain,
        "decision_sequence_validation": sequence_validation,
        "decision_duplicate_rejection": duplicate_rejection,
        "decision_sensitive_field_exclusion": sensitive_exclusion,
    }
