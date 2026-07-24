"""
Data models for the Versioned Benchmark DSL.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Assertion:
    type: str
    target: str = "output"
    value: Any | None = None


@dataclass(frozen=True)
class Step:
    role: str
    content: str
    assertions: list[Assertion] = field(default_factory=list)


@dataclass(frozen=True)
class Scenario:
    id: str
    version: str
    title: str
    category: str
    steps: list[Step]
    metadata: dict[str, Any] = field(default_factory=dict)
    fingerprint: str | None = None
