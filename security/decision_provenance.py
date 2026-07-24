# security/decision_provenance.py

"""
Decision Provenance Engine.

Formalizes the invariant:
  "Every decision that crosses a trust boundary should be deterministic, least-privileged,
   auditable, and backed by verifiable evidence."

Binds authorization and evaluation decisions into immutable, cryptographically hashed records:
  - decision_id
  - correlation_id
  - timestamp (ISO-8601 UTC)
  - policy_version
  - identity (tenant_id, user_id)
  - resource_id & action
  - verdict (ALLOW, DENY, PASS, FAIL)
  - SHA-256 cryptographic provenance digest
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


class DecisionProvenanceError(ValueError):
    """Raised when a decision record fails provenance or tamper verification."""


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    decision_id: str
    correlation_id: str
    timestamp: str
    policy_version: str
    evaluator_version: str
    tenant_id: str
    user_id: str
    resource_id: str
    action: str
    verdict: str
    digest: str

    @classmethod
    def create(
        cls,
        *,
        decision_id: str,
        correlation_id: str,
        policy_version: str = "1.0.0",
        evaluator_version: str = "1.0.0",
        tenant_id: str,
        user_id: str,
        resource_id: str,
        action: str,
        verdict: str,
        timestamp: str | None = None,
    ) -> DecisionRecord:
        ts = timestamp or datetime.now(UTC).isoformat().replace("+00:00", "Z")
        payload = {
            "decision_id": decision_id,
            "correlation_id": correlation_id,
            "timestamp": ts,
            "policy_version": policy_version,
            "evaluator_version": evaluator_version,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "resource_id": resource_id,
            "action": action,
            "verdict": verdict,
        }
        canonical_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        digest = hashlib.sha256(canonical_bytes).hexdigest()
        return cls(
            decision_id=decision_id,
            correlation_id=correlation_id,
            timestamp=ts,
            policy_version=policy_version,
            evaluator_version=evaluator_version,
            tenant_id=tenant_id,
            user_id=user_id,
            resource_id=resource_id,
            action=action,
            verdict=verdict,
            digest=digest,
        )

    def verify(self) -> bool:
        """Re-computes and verifies the cryptographic provenance digest."""
        payload = {
            "decision_id": self.decision_id,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "policy_version": self.policy_version,
            "evaluator_version": self.evaluator_version,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "resource_id": self.resource_id,
            "action": self.action,
            "verdict": self.verdict,
        }
        expected = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        if self.digest != expected:
            raise DecisionProvenanceError("Decision record digest mismatch (tampering detected)")
        return True
