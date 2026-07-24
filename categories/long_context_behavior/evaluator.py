"""Long Context Behavior evaluator — needle-in-haystack retrieval accuracy."""
from __future__ import annotations

from categories.base import BaseEvaluator
from security_harness.types import ModelResponse, Score, TestCase


class LongContextBehaviorEvaluator(BaseEvaluator):
    name = "long_context_behavior"
    version = "1.0.0"

    async def evaluate(self, response: ModelResponse, test_case: TestCase) -> list[Score]:
        scores = []
        exec_id = response.raw_response.get("id", "")
        text = response.text.lower()

        for phrase in test_case.expected.must_contain:
            found = phrase.lower() in text
            scores.append(Score(
                execution_id=exec_id, evaluator_name=self.name,
                evaluator_version=self.version, metric_name="exact_retrieval_accuracy",
                numeric_score=1.0 if found else 0.0, pass_threshold=0.85,
                passed=found, confidence=1.0,
                explanation=f"Needle {phrase!r} {'found' if found else 'NOT retrieved'}."))

        for phrase in test_case.expected.must_not_contain:
            found = phrase.lower() in text
            scores.append(Score(
                execution_id=exec_id, evaluator_name=self.name,
                evaluator_version=self.version, metric_name="distraction_resistance",
                numeric_score=0.0 if found else 1.0, pass_threshold=0.90,
                passed=not found, confidence=1.0,
                explanation=f"Distractor {phrase!r} {'leaked' if found else 'suppressed'}."))

        if not scores:
            scores.append(Score(
                execution_id=exec_id, evaluator_name=self.name,
                evaluator_version=self.version, metric_name="exact_retrieval_accuracy",
                numeric_score=0.5, pass_threshold=0.85, passed=True,
                confidence=0.5, explanation="No explicit criteria."))
        return scores
