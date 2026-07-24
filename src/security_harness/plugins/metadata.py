# src/security_harness/plugins/metadata.py

from __future__ import annotations

from dataclasses import dataclass

from .capabilities import ModelCapabilities


@dataclass(frozen=True)
class ProviderMetadata:
    provider_name: str
    plugin_version: str
    api_version: str
    models: tuple[ModelCapabilities, ...]
    homepage: str | None = None

    def model(self, model_id: str) -> ModelCapabilities:
        for item in self.models:
            if item.model == model_id:
                return item

        raise KeyError(
            f"Provider '{self.provider_name}' does not expose model '{model_id}'."
        )
