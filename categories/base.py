"""
Category base classes.

All evaluation categories implement BaseCategory and expose a BaseEvaluator
that produces Score records for each test case execution.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from security_harness.types import ModelResponse, Score, TestCase


class BaseEvaluator(ABC):
    """
    Abstract evaluator. Each category provides a concrete subclass.

    evaluate() is the only required method. It receives the model response
    and the original test case, and returns a list of Score records
    (one per metric the category tracks).
    """

    name: str          # e.g., "guardrail_consistency"
    version: str = "1.0.0"

    @abstractmethod
    async def evaluate(
        self,
        response: ModelResponse,
        test_case: TestCase,
    ) -> list[Score]:
        """
        Evaluate a single model response against a test case.

        Args:
            response:  Normalised, redacted ModelResponse.
            test_case: The test case that was run.

        Returns:
            List of Score records (one per metric).
        """


class BaseCategory(ABC):
    """
    Abstract category. Exposes metadata and produces an evaluator instance.
    """

    name: str           # e.g., "guardrail_consistency"
    display_name: str   # e.g., "Guardrail Consistency"
    description: str

    @abstractmethod
    def get_evaluator(self) -> BaseEvaluator:
        """Return the evaluator for this category."""

    @abstractmethod
    def load_cases(self) -> list[TestCase]:
        """Load and validate test cases from this category's cases/ directory."""
