"""
Plugin protocol contracts and interfaces for dynamic multi-model harness extensions.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable, Any, Dict
from dataclasses import dataclass, field


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

    def create_adapter(self, config: Dict[str, Any]) -> Any:
        ...
