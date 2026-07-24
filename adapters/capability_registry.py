"""
Capability registry — maps model identifiers to their feature support flags.

Used by the runner to skip test cases that require capabilities a model does not have
(e.g., skip tool-use tests for models that don't support tool calling).
"""

from __future__ import annotations

from dataclasses import dataclass

import yaml


@dataclass(frozen=True)
class ModelCapabilities:
    model: str
    provider: str
    context_limit: int
    max_output_tokens: int
    supports_tools: bool
    supports_system_messages: bool
    supports_json_schema: bool


class CapabilityRegistry:
    """
    Loaded from models.yaml. Provides fast lookup of model capabilities.

    Usage:
        registry = CapabilityRegistry.from_config()
        caps = registry.get("gpt-4o")
        if caps.supports_tools:
            ...
    """

    def __init__(self, capabilities: dict[str, ModelCapabilities]) -> None:
        self._capabilities = capabilities

    @classmethod
    def from_config(cls, config_path: str = "config/models.yaml") -> CapabilityRegistry:
        try:
            with open(config_path) as f:
                raw = yaml.safe_load(f) or {}
        except FileNotFoundError:
            return cls({})

        caps: dict[str, ModelCapabilities] = {}
        for provider, models in raw.items():
            for model_name, meta in models.items():
                caps[model_name] = ModelCapabilities(
                    model=model_name,
                    provider=provider,
                    context_limit=meta.get("context_limit", 4096),
                    max_output_tokens=meta.get("max_output_tokens", 800),
                    supports_tools=meta.get("supports_tools", False),
                    supports_system_messages=meta.get("supports_system_messages", True),
                    supports_json_schema=meta.get("supports_json_schema", False),
                )
        return cls(caps)

    def get(self, model: str) -> ModelCapabilities | None:
        """Return capabilities for a model, or None if unknown."""
        return self._capabilities.get(model)

    def all_models(self) -> list[ModelCapabilities]:
        return list(self._capabilities.values())

    def models_for_provider(self, provider: str) -> list[ModelCapabilities]:
        return [c for c in self._capabilities.values() if c.provider == provider]
