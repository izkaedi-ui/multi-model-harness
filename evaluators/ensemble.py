"""
Judge Ensemble implementation supporting weighted voting, consensus, and deterministic tie breaking.
"""
from __future__ import annotations

import logging
from typing import List, Dict, Optional
from evaluators.contracts import EvaluatorResult, EnsembleVerdict
from security_harness.errors import ConfigurationError

logger = logging.getLogger(__name__)


class JudgeEnsemble:
    """Consolidates results from multiple evaluators using weighted voting or consensus strategies."""

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        strategy: str = "weighted_majority",
        missing_judge_policy: str = "fail_closed",
    ) -> None:
        self.weights = weights or {}
        self.strategy = strategy
        self.missing_judge_policy = missing_judge_policy

        if strategy not in ("weighted_majority", "consensus", "unanimous"):
            raise ConfigurationError(f"Unsupported ensemble strategy: {strategy!r}")

    def consolidate(self, results: List[EvaluatorResult]) -> EnsembleVerdict:
        """Consolidate individual evaluator results into an EnsembleVerdict."""
        if not results:
            if self.missing_judge_policy == "fail_closed":
                return EnsembleVerdict(
                    passed=False,
                    final_score=0.0,
                    strategy=self.strategy,
                    agreement_ratio=0.0,
                    disagreement_reported=True,
                    judge_results=[],
                    metadata={"error": "Empty judge results payload"},
                )
            raise ConfigurationError("Cannot consolidate empty judge results")

        # Validate weights
        for r in results:
            w = self.weights.get(r.judge_id, 1.0)
            if w < 0.0:
                raise ConfigurationError(f"Invalid negative weight for judge '{r.judge_id}': {w}")

        total_weight = 0.0
        passed_weight = 0.0
        scores: List[float] = []

        pass_count = sum(1 for r in results if r.passed)
        total_judges = len(results)

        for r in results:
            weight = self.weights.get(r.judge_id, 1.0)
            total_weight += weight
            if r.passed:
                passed_weight += weight
            scores.append(r.score)

        avg_score = sum(scores) / total_judges
        agreement_ratio = max(pass_count, total_judges - pass_count) / total_judges
        disagreement = (pass_count > 0 and pass_count < total_judges)

        tie_broken = False
        if self.strategy in ("weighted_majority", "majority"):
            half_weight = total_weight / 2.0
            if passed_weight > half_weight:
                final_pass = True
            elif passed_weight < half_weight:
                final_pass = False
            else:
                # Deterministic tie-breaker: True if avg_score >= 0.5
                final_pass = (avg_score >= 0.5)
                tie_broken = True
        elif self.strategy in ("consensus", "unanimous"):
            final_pass = (pass_count == total_judges)

        return EnsembleVerdict(
            passed=final_pass,
            final_score=avg_score,
            strategy=self.strategy,
            agreement_ratio=agreement_ratio,
            disagreement_reported=disagreement,
            judge_results=results,
            tie_broken=tie_broken,
            metadata={
                "total_judges": total_judges,
                "passed_weight": passed_weight,
                "total_weight": total_weight,
            },
        )
