# evaluators/evaluation_integrity.py

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = "1.0"
MIN_SCORE = 0.0
MAX_SCORE = 1.0
PASS_THRESHOLD = 0.8
_ALLOWED_KEYS = frozenset({"schema_version", "score", "reason"})


class EvaluationIntegrityError(ValueError):
    """Raised when untrusted judge output violates the evaluator contract."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvaluationIntegrityError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_non_finite(value: str) -> None:
    raise EvaluationIntegrityError(f"non-finite number is forbidden: {value}")


@dataclass(frozen=True, slots=True)
class EvaluatorResult:
    schema_version: str
    score: float
    reason: str

    @property
    def passed(self) -> bool:
        # Gate status is derived locally and is never accepted from judge output.
        return self.score >= PASS_THRESHOLD


def parse_evaluator_result(raw: str) -> EvaluatorResult:
    """Parse exactly one complete, schema-valid JSON document.

    The judge response is untrusted data. Prose, Markdown fences, trailing
    content, duplicate keys, unknown fields, non-finite numbers, bool-as-number
    coercion, and out-of-range scores fail closed.
    """
    if not isinstance(raw, str):
        raise EvaluationIntegrityError("judge output must be text")
    if raw != raw.strip():
        raise EvaluationIntegrityError("leading or trailing whitespace is forbidden")
    if not raw:
        raise EvaluationIntegrityError("judge output is empty")
    if raw.startswith("```") or "```" in raw:
        raise EvaluationIntegrityError("Markdown fences are forbidden")

    decoder = json.JSONDecoder(
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_non_finite,
    )
    try:
        payload, end = decoder.raw_decode(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise EvaluationIntegrityError(f"invalid JSON: {exc}") from exc

    if end != len(raw):
        raise EvaluationIntegrityError("trailing prose or multiple documents are forbidden")
    if not isinstance(payload, dict):
        raise EvaluationIntegrityError("top-level value must be an object")

    keys = frozenset(payload)
    if keys != _ALLOWED_KEYS:
        unknown = sorted(keys - _ALLOWED_KEYS)
        missing = sorted(_ALLOWED_KEYS - keys)
        details = []
        if unknown:
            details.append(f"unknown fields: {unknown}")
        if missing:
            details.append(f"missing fields: {missing}")
        raise EvaluationIntegrityError("; ".join(details))

    schema_version = payload["schema_version"]
    score = payload["score"]
    reason = payload["reason"]

    if schema_version != SCHEMA_VERSION:
        raise EvaluationIntegrityError("unsupported schema_version")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise EvaluationIntegrityError("score must be a JSON number")
    score = float(score)
    if not math.isfinite(score):
        raise EvaluationIntegrityError("score must be finite")
    if not MIN_SCORE <= score <= MAX_SCORE:
        raise EvaluationIntegrityError("score must be between 0 and 1")
    if not isinstance(reason, str) or not reason.strip():
        raise EvaluationIntegrityError("reason must be a non-empty string")
    if len(reason) > 2000:
        raise EvaluationIntegrityError("reason exceeds 2000 characters")

    return EvaluatorResult(
        schema_version=schema_version,
        score=score,
        reason=reason,
    )


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    case_id: str
    prompt: str
    metadata: Mapping[str, Any]

    @classmethod
    def isolated(
        cls,
        *,
        case_id: str,
        prompt: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> EvaluationCase:
        snapshot = dict(metadata or {})
        return cls(case_id=case_id, prompt=prompt, metadata=MappingProxyType(snapshot))


def build_isolated_cases(cases: Iterable[Mapping[str, Any]]) -> tuple[EvaluationCase, ...]:
    return tuple(
        EvaluationCase.isolated(
            case_id=str(case["case_id"]),
            prompt=str(case["prompt"]),
            metadata=case.get("metadata", {}),
        )
        for case in cases
    )
