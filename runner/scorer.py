"""Scorer — dispatches responses to the correct per-category evaluator."""
from __future__ import annotations

import logging

from categories.registry import CategoryRegistry
from security_harness.types import ModelResponse, Score, TestCase

log = logging.getLogger(__name__)

class Scorer:
    def __init__(self, registry: CategoryRegistry) -> None:
        self._registry = registry

    async def score(self, response: ModelResponse, test_case: TestCase) -> list[Score]:
        try:
            category = self._registry.get(test_case.category)
            evaluator = category.get_evaluator()
            scores = await evaluator.evaluate(response, test_case)
            log.debug("scorer.scored", extra={"case_id": test_case.id, "n_scores": len(scores)})
            return scores
        except Exception as exc:
            log.error("scorer.failed", extra={"case_id": test_case.id, "error": str(exc)})
            return []
