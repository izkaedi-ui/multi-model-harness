"""Guardrail Consistency category — category descriptor and case loader."""

from __future__ import annotations

import json
import pathlib

from categories.base import BaseCategory, BaseEvaluator
from categories.guardrail_consistency.evaluator import GuardrailConsistencyEvaluator
from security_harness.types import ExpectedBehavior, RiskLevel, TestCase

_CASES_DIR = pathlib.Path(__file__).parent / "cases"


class GuardrailConsistencyCategory(BaseCategory):
    name = "guardrail_consistency"
    display_name = "Guardrail Consistency"
    description = (
        "Measures whether a model's refusal decisions are consistent across "
        "surface-level transformations, languages, and repeated sampling."
    )

    def get_evaluator(self) -> BaseEvaluator:
        return GuardrailConsistencyEvaluator()

    def load_cases(self) -> list[TestCase]:
        cases: list[TestCase] = []
        for jsonl_file in sorted(_CASES_DIR.glob("*.jsonl")):
            with jsonl_file.open(encoding="utf-8") as f:
                for line in f:

                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    raw = json.loads(line)
                    cases.append(_parse_case(raw))
        return cases


def _parse_case(raw: dict) -> TestCase:
    exp = raw.get("expected", {})
    return TestCase(
        id=raw["id"],
        version=raw.get("version", 1),
        category=raw["category"],
        subcategory=raw["subcategory"],
        description=raw.get("description", ""),
        messages=tuple(raw["messages"]),
        expected=ExpectedBehavior(
            must_contain=tuple(exp.get("must_contain", [])),
            must_not_contain=tuple(exp.get("must_not_contain", [])),
            expected_behavior=exp.get("expected_behavior", ""),
        ),
        follow_up_messages=tuple(raw.get("follow_up_messages", [])),
        tags=tuple(raw.get("tags", [])),
        risk_level=RiskLevel(raw.get("risk_level", "low")),
    )
