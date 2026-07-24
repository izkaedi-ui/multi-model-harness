"""Prompt Robustness category."""
from __future__ import annotations
import json, pathlib
from categories.base import BaseCategory, BaseEvaluator
from categories.prompt_robustness.evaluator import PromptRobustnessEvaluator
from security_harness.types import ExpectedBehavior, RiskLevel, TestCase

_CASES_DIR = pathlib.Path(__file__).parent / "cases"

class PromptRobustnessCategory(BaseCategory):
    name = "prompt_robustness"
    display_name = "Prompt Robustness"
    description = "Verifies that the model's responses are semantically consistent across surface-level prompt transformations (typos, whitespace, unicode, paraphrases)."

    def get_evaluator(self) -> BaseEvaluator:
        return PromptRobustnessEvaluator()

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
