"""
Evaluator Protocol Contracts for Stage 3A.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class EvaluatorResult:
    """Typed result from an individual evaluator or judge."""
    judge_id: str
    passed: bool
    score: float  # Normalized 0.0 - 1.0
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EnsembleVerdict:
    """Consolidated verdict from a judge ensemble."""
    passed: bool
    final_score: float
    strategy: str
    agreement_ratio: float
    disagreement_reported: bool
    judge_results: list[EvaluatorResult]
    tie_broken: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class EvaluatorProtocol(Protocol):
    """Protocol that all judge evaluators must implement."""

    @property
    def judge_id(self) -> str:
        ...

    def evaluate(self, input_prompt: str, response_text: str, expected: Any | None = None) -> EvaluatorResult:
        ...
