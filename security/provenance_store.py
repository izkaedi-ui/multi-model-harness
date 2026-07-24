# security/provenance_store.py

"""
Atomic Append-Only Persistence Store for Decision Provenance Chains (Level 4).

Guarantees:
  1. Monotonic stream sequences: (stream_id, stream_sequence) primary key.
  2. Digest link integrity: previous_record_digest == current_record_digest of prior record.
  3. Unique decision_id enforcement.
  4. Atomic compare-and-append (rollback on conflict or failed verification).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Sequence

from cryptography.hazmat.primitives.asymmetric import ed25519

from security.decision_provenance import (
    DecisionProvenanceError,
    DecisionRecord,
    ProvenanceChain,
)


class ProvenanceStore:
    """Atomic SQLite-backed append-only provenance log."""

    def __init__(self, db_path: str = "database/provenance_store.db") -> None:
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        conn = self._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS decision_provenance_stream (
                    stream_id TEXT NOT NULL,
                    stream_sequence INTEGER NOT NULL,
                    decision_id TEXT NOT NULL UNIQUE,
                    correlation_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    evaluator_version TEXT NOT NULL,
                    previous_record_digest TEXT NOT NULL,
                    current_record_digest TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    signing_key_id TEXT NOT NULL,
                    algorithm TEXT NOT NULL,
                    canonical_payload_json TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    canonicalization_version TEXT NOT NULL,
                    PRIMARY KEY (stream_id, stream_sequence)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_stream_decision_id
                ON decision_provenance_stream(decision_id)
            """)
            conn.commit()
        finally:
            conn.close()

    def append(
        self,
        stream_id: str,
        record: DecisionRecord,
        key_or_public_key: bytes | ed25519.Ed25519PublicKey,
    ) -> bool:
        """
        Atomically appends a verified DecisionRecord to stream_id.
        Fails closed and rolls back on sequence gaps, digest breaks, duplicate IDs, or signature failures.
        """
        # 1. Level 1 & 2 Verification
        record.verify_signature(key_or_public_key)

        conn = self._get_connection()
        try:
            conn.execute("BEGIN TRANSACTION")

            # 2. Query current stream head
            cursor = conn.execute(
                """
                SELECT stream_sequence, current_record_digest
                FROM decision_provenance_stream
                WHERE stream_id = ?
                ORDER BY stream_sequence DESC
                LIMIT 1
                """,
                (stream_id,),
            )
            head = cursor.fetchone()

            if head is None:
                # Initial record in stream
                if record.stream_sequence != 1:
                    raise DecisionProvenanceError(f"First record in stream '{stream_id}' must have stream_sequence=1")
                if record.previous_record_digest != "GENESIS":
                    raise DecisionProvenanceError(f"First record in stream '{stream_id}' must have previous_record_digest='GENESIS'")
            else:
                head_seq, head_digest = head
                expected_seq = head_seq + 1
                if record.stream_sequence != expected_seq:
                    raise DecisionProvenanceError(
                        f"Optimistic concurrency failure in stream '{stream_id}': expected sequence {expected_seq}, got {record.stream_sequence}"
                    )
                if record.previous_record_digest != head_digest:
                    raise DecisionProvenanceError(
                        f"Digest link break in stream '{stream_id}': expected previous_record_digest='{head_digest}', got '{record.previous_record_digest}'"
                    )

            # 3. Payload JSON for storage
            payload_json = json.dumps(record._build_canonical_payload(), sort_keys=True)

            # 4. Atomic SQL Insert
            conn.execute(
                """
                INSERT INTO decision_provenance_stream (
                    stream_id, stream_sequence, decision_id, correlation_id, tenant_id,
                    user_id, resource_id, action, verdict, policy_version, evaluator_version,
                    previous_record_digest, current_record_digest, signature, signing_key_id,
                    algorithm, canonical_payload_json, timestamp, schema_version, canonicalization_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stream_id,
                    record.stream_sequence,
                    record.decision_id,
                    record.correlation_id,
                    record.tenant_id,
                    record.user_id,
                    record.resource_id,
                    record.action,
                    record.verdict,
                    record.policy_version,
                    record.evaluator_version,
                    record.previous_record_digest,
                    record.current_record_digest,
                    record.signature,
                    record.signing_key_id,
                    record.algorithm,
                    payload_json,
                    record.timestamp,
                    record.schema_version,
                    record.canonicalization_version,
                ),
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            if isinstance(e, DecisionProvenanceError):
                raise
            elif isinstance(e, sqlite3.IntegrityError):
                raise DecisionProvenanceError(f"Duplicate decision_id or stream sequence constraint failure: {e}") from e
            else:
                raise DecisionProvenanceError(f"Failed to append record to stream '{stream_id}': {e}") from e
        finally:
            conn.close()

    def get_stream_head(self, stream_id: str) -> tuple[int, str] | None:
        """Returns (max_sequence, max_digest) for stream_id or None if empty."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT stream_sequence, current_record_digest
                FROM decision_provenance_stream
                WHERE stream_id = ?
                ORDER BY stream_sequence DESC
                LIMIT 1
                """,
                (stream_id,),
            )
            row = cursor.fetchone()
            return (row[0], row[1]) if row else None
        finally:
            conn.close()

    def get_stream_records(self, stream_id: str) -> list[DecisionRecord]:
        """Fetches and reconstructs all DecisionRecords for stream_id in order."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT decision_id, correlation_id, timestamp, schema_version,
                       canonicalization_version, policy_version, evaluator_version,
                       tenant_id, user_id, resource_id, action, verdict,
                       stream_sequence, previous_record_digest, current_record_digest,
                       signature, signing_key_id, algorithm
                FROM decision_provenance_stream
                WHERE stream_id = ?
                ORDER BY stream_sequence ASC
                """,
                (stream_id,),
            )
            rows = cursor.fetchall()
            records: list[DecisionRecord] = []
            for row in rows:
                rec = DecisionRecord(
                    decision_id=row[0],
                    correlation_id=row[1],
                    timestamp=row[2],
                    schema_version=row[3],
                    canonicalization_version=row[4],
                    policy_version=row[5],
                    evaluator_version=row[6],
                    tenant_id=row[7],
                    user_id=row[8],
                    resource_id=row[9],
                    action=row[10],
                    verdict=row[11],
                    stream_sequence=row[12],
                    previous_record_digest=row[13],
                    current_record_digest=row[14],
                    signature=row[15],
                    signing_key_id=row[16],
                    algorithm=row[17],
                )
                records.append(rec)
            return records
        finally:
            conn.close()

    def verify_stored_stream(
        self,
        stream_id: str,
        key_or_public_key: bytes | ed25519.Ed25519PublicKey,
    ) -> bool:
        """Loads and validates the complete audit chain for stream_id."""
        records = self.get_stream_records(stream_id)
        if not records:
            raise DecisionProvenanceError(f"No records found for stream '{stream_id}'")
        return ProvenanceChain.validate_chain(records, signing_key_or_public_key=key_or_public_key)
