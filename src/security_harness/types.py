"""
Shared data contracts for the security test harness.

All types are frozen dataclasses — treat instances as immutable values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    BUDGET_EXCEEDED = "budget_exceeded"



class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    TIMED_OUT = "timed_out"
    SKIPPED = "skipped"


class VerdictStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    NEEDS_REVIEW = "needs_review"
    INCONCLUSIVE = "inconclusive"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Request / Response
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int

    @classmethod
    def empty(cls) -> TokenUsage:
        return cls(input_tokens=0, output_tokens=0, total_tokens=0)


@dataclass(frozen=True)
class ModelRequest:
    """Normalised request sent to a provider adapter."""

    model: str
    messages: tuple[dict[str, str], ...]
    temperature: float
    max_output_tokens: int
    tools: tuple[dict[str, Any], ...] | None = None
    system_prompt: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.model:
            raise ValueError("model must not be empty")
        if not self.messages:
            raise ValueError("messages must not be empty")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError(f"temperature {self.temperature!r} out of [0.0, 2.0]")


@dataclass(frozen=True)
class ModelResponse:
    """Normalised response returned by a provider adapter."""

    provider: str
    model: str
    text: str
    finish_reason: str | None
    tool_calls: tuple[dict[str, Any], ...]
    usage: TokenUsage
    latency_ms: int
    raw_response: dict[str, Any]

    # Set by the redactor after normalization
    redaction_applied: bool = False


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExpectedBehavior:
    """Criteria that the evaluator checks against the model response."""

    must_contain: tuple[str, ...] = ()
    must_not_contain: tuple[str, ...] = ()
    expected_behavior: str = ""
    # JSON Schema the response must satisfy (for structured output tests)
    json_schema: dict[str, Any] | None = None
    # Approximate expected text for semantic similarity checks
    approximate_match: str | None = None


@dataclass(frozen=True)
class TestCase:
    """
    Immutable, versioned test case record.

    Test cases are loaded from JSONL files in categories/*/cases/*.jsonl.
    Use synthetic markers — never real credentials or PII.
    """

    id: str
    version: int
    category: str
    subcategory: str
    description: str
    messages: tuple[dict[str, str], ...]
    expected: ExpectedBehavior
    follow_up_messages: tuple[dict[str, str], ...] = ()
    tags: tuple[str, ...] = ()
    risk_level: RiskLevel = RiskLevel.LOW
    content_hash: str = ""  # SHA-256 of canonical JSON; set by loader

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("TestCase.id must not be empty")
        if not self.category:
            raise ValueError("TestCase.category must not be empty")
        if not self.messages:
            raise ValueError("TestCase.messages must not be empty")


# ---------------------------------------------------------------------------
# Scoring and verdicts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Score:
    """A single metric score produced by an evaluator."""

    execution_id: str
    evaluator_name: str
    evaluator_version: str
    metric_name: str
    numeric_score: float          # 0.0 – 1.0
    pass_threshold: float
    passed: bool
    confidence: float             # 0.0 – 1.0
    explanation: str = ""


@dataclass(frozen=True)
class Verdict:
    """Aggregated pass/fail decision for one execution."""

    execution_id: str
    status: VerdictStatus
    severity: RiskLevel
    confidence: float
    requires_human_review: bool
    review_notes: str = ""
    blocking_metric: str | None = None  # Name of the metric that caused a FAIL
