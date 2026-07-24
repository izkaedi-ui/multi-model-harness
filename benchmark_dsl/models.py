"""
Data models for the Versioned Benchmark DSL.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass(frozen=True)
class Assertion:
    type: str
    target: str = "output"
    value: Optional[Any] = None


@dataclass(frozen=True)
class Step:
    role: str
    content: str
    assertions: List[Assertion] = field(default_factory=list)


@dataclass(frozen=True)
class Scenario:
    id: str
    version: str
    title: str
    category: str
    steps: List[Step]
    metadata: Dict[str, Any] = field(default_factory=dict)
    fingerprint: Optional[str] = None
