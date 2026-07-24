"""
Plugin protocol contracts and interfaces for dynamic multi-model harness extensions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class PluginMetadata:
    """Immutable metadata describing an installed harness plugin."""
    name: str
    version: str
    description: str
    author: str = ""
    capabilities: list[str] = field(default_factory=list)


@runtime_checkable
class ProviderPluginProtocol(Protocol):
    """Protocol contract that all dynamic provider plugins must satisfy."""

    @property
    def metadata(self) -> PluginMetadata:
        ...

    def create_adapter(self, config: dict[str, Any]) -> Any:
        ...
