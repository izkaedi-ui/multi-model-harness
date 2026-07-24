"""
Database repository — typed async CRUD operations.

All public methods are async and operate within explicit transactions.
Never call raw SQL outside this module — use repository methods.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime

import aiosqlite

from database.transactions import async_transaction
from security_harness.types import (
    ExecutionStatus,
    RunStatus,
    Score,
    Verdict,
)

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _uid() -> str:
    return uuid.uuid4().hex


class HarnessRepository:
    """
    Typed repository for all harness database operations.

    Usage:
        repo = HarnessRepository(conn)
        await repo.save_run(run_id, ...)
    """

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    async def create_run(
        self,
        run_id: str,
        correlation_id: str,
        budget_limit_usd: float = 35.0,
        estimated_cost_usd: float = 0.0,
    ) -> None:
        async with async_transaction(self._conn):
            await self._conn.execute(
                """
                INSERT INTO runs (id, correlation_id, status, started_at,
                                  budget_limit_usd, estimated_cost_usd)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, correlation_id, RunStatus.RUNNING.value, _now(),
                 budget_limit_usd, estimated_cost_usd),
            )

    async def update_run_status(
        self,
        run_id: str,
        status: RunStatus,
        actual_cost_usd: float = 0.0,
        failure_reason: str | None = None,
    ) -> None:
        async with async_transaction(self._conn):
            await self._conn.execute(
                """
                UPDATE runs
                SET status = ?, completed_at = ?, actual_cost_usd = ?, failure_reason = ?
                WHERE id = ?
                """,
                (status.value, _now(), actual_cost_usd, failure_reason, run_id),
            )

    # ------------------------------------------------------------------
    # Executions
    # ------------------------------------------------------------------

    async def save_execution(
        self,
        execution_id: str,
        run_id: str,
        test_case_id: str,
        model_id: str,
        status: ExecutionStatus,
        latency_ms: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        finish_reason: str | None = None,
        estimated_cost_usd: float = 0.0,
    ) -> None:
        async with async_transaction(self._conn):
            await self._conn.execute(
                """
                INSERT INTO executions
                    (id, run_id, test_case_id, model_id, status, response_timestamp,
                     latency_ms, input_tokens, output_tokens, finish_reason, estimated_cost_usd)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (execution_id, run_id, test_case_id, model_id, status.value, _now(),
                 latency_ms, input_tokens, output_tokens, finish_reason, estimated_cost_usd),
            )

    # ------------------------------------------------------------------
    # Scores
    # ------------------------------------------------------------------

    async def save_scores(self, scores: list[Score]) -> None:
        async with async_transaction(self._conn):
            for score in scores:
                await self._conn.execute(
                    """
                    INSERT INTO scores
                        (id, execution_id, evaluator_name, evaluator_version,
                         metric_name, numeric_score, pass_threshold, passed,
                         confidence, explanation)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (_uid(), score.execution_id, score.evaluator_name,
                     score.evaluator_version, score.metric_name,
                     score.numeric_score, score.pass_threshold,
                     int(score.passed), score.confidence, score.explanation),
                )

    # ------------------------------------------------------------------
    # Verdicts
    # ------------------------------------------------------------------

    async def save_verdict(self, verdict: Verdict) -> None:
        async with async_transaction(self._conn):
            await self._conn.execute(
                """
                INSERT INTO verdicts
                    (id, execution_id, status, severity, confidence,
                     requires_human_review, review_notes, blocking_metric)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (_uid(), verdict.execution_id, verdict.status.value,
                 verdict.severity.value, verdict.confidence,
                 int(verdict.requires_human_review), verdict.review_notes,
                 verdict.blocking_metric),
            )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def list_runs(self, limit: int = 50) -> list[dict]:
        cursor = await self._conn.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_run_summary(self, run_id: str) -> dict | None:
        cursor = await self._conn.execute(
            "SELECT * FROM runs WHERE id = ?", (run_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
