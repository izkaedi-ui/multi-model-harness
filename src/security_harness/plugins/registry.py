"""
Plugin registry for dynamic provider plugin discovery and loading.
"""
from __future__ import annotations

import logging
from importlib.metadata import entry_points
from typing import Dict, Any, Optional

from src.security_harness.plugins.contracts import PluginMetadata, ProviderPluginProtocol

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "multi_model_harness.providers"


class PluginRegistry:
    """Discovers and loads provider plugins via Python entry points."""

    def __init__(self, entry_point_group: str = ENTRY_POINT_GROUP) -> None:
        self.entry_point_group = entry_point_group
        self._loaded_plugins: Dict[str, Any] = {}

    def discover(self) -> list[str]:
        """Return list of discovered plugin names in the entry point group."""
        try:
            eps = entry_points(group=self.entry_point_group)
            return [ep.name for ep in eps]
        except Exception as e:
            logger.warning(f"Error discovering plugins for group {self.entry_point_group}: {e}")
            return []

    def load_plugin(self, name: str) -> Optional[Any]:
        """Load and return a single provider plugin by name."""
        if name in self._loaded_plugins:
            return self._loaded_plugins[name]

        try:
            eps = entry_points(group=self.entry_point_group)
            plugins_map = {ep.name: ep for ep in eps}
            if name not in plugins_map:
                logger.debug(f"Plugin '{name}' not found in entry point group '{self.entry_point_group}'")
                return None

            plugin_cls = plugins_map[name].load()
            instance = plugin_cls()
            self._loaded_plugins[name] = instance
            return instance
        except Exception as e:
            logger.error(f"Failed to load provider plugin '{name}': {e}")
            return None

    def load_all(self) -> Dict[str, Any]:
        """Discover and load all registered provider plugins."""
        for name in self.discover():
            self.load_plugin(name)
        return dict(self._loaded_plugins)
