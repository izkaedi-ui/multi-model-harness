"""Long Context Behavior category."""
from __future__ import annotations

import json
import pathlib

from categories.base import BaseCategory, BaseEvaluator
from categories.long_context_behavior.evaluator import LongContextBehaviorEvaluator
from security_harness.types import ExpectedBehavior, RiskLevel, TestCase

_CASES_DIR = pathlib.Path(__file__).parent / "cases"

class LongContextBehaviorCategory(BaseCategory):
    name = "long_context_behavior"
    display_name = "Long-Context Behavior"
    description = "Tests retrieval accuracy, recall, contradiction detection, and distraction resistance in long document contexts."

    def get_evaluator(self) -> BaseEvaluator:
        return LongContextBehaviorEvaluator()

    def load_cases(self) -> list[TestCase]:
        cases = []
        for jsonl_file in sorted(_CASES_DIR.glob("*.jsonl")):
            with jsonl_file.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"): continue
                    raw = json.loads(line)
                    exp = raw.get("expected", {})
                    cases.append(TestCase(
                        id=raw["id"], version=raw.get("version", 1),
                        category=raw["category"], subcategory=raw["subcategory"],
                        description=raw.get("description", ""),
                        messages=tuple(raw["messages"]),
                        expected=ExpectedBehavior(
                            must_contain=tuple(exp.get("must_contain", [])),
                            must_not_contain=tuple(exp.get("must_not_contain", [])),
                            expected_behavior=exp.get("expected_behavior", ""),
                        ),
                        tags=tuple(raw.get("tags", [])),
                        risk_level=RiskLevel(raw.get("risk_level", "low")),
                    ))
        return cases
