# src/security_harness/plugins/capabilities.py

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Capability(StrEnum):
    TEXT = "text"
    VISION = "vision"
    AUDIO = "audio"
    TOOLS = "tools"
    JSON = "json"
    STREAMING = "streaming"
    REASONING = "reasoning"
    EMBEDDINGS = "embeddings"
    LONG_CONTEXT = "long_context"


@dataclass(frozen=True)
class ModelCapabilities:
    model: str
    context_window: int
    max_output_tokens: int
    capabilities: frozenset[Capability] = field(default_factory=frozenset)

    def supports(self, capability: Capability) -> bool:
        return capability in self.capabilities
