"""
Unit tests for PluginRegistry and dynamic ProviderPlugin Protocol contracts.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from adapters.provider_factory import build_adapter
from security_harness.errors import ConfigurationError
from src.security_harness.plugins.contracts import PluginMetadata, ProviderPluginProtocol
from src.security_harness.plugins.registry import PluginRegistry


class MockCustomPlugin:
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="mock_provider",
            version="1.0.0",
            description="Mock provider plugin for testing",
        )

    def create_adapter(self, config: dict) -> MagicMock:
        mock_adapter = MagicMock()
        mock_adapter.provider_name = "mock_provider"
        return mock_adapter


class TestPluginRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = PluginRegistry()

    def test_plugin_metadata_creation(self):
        meta = PluginMetadata(
            name="custom",
            version="0.1.0",
            description="Custom provider",
            capabilities=["chat"],
        )
        self.assertEqual(meta.name, "custom")
        self.assertEqual(meta.version, "0.1.0")
        self.assertIn("chat", meta.capabilities)

    def test_protocol_conformance(self):
        plugin = MockCustomPlugin()
        self.assertTrue(isinstance(plugin, ProviderPluginProtocol))

    @patch("src.security_harness.plugins.registry.entry_points")
    def test_discover_plugins(self, mock_entry_points):
        mock_ep = MagicMock()
        mock_ep.name = "mock_provider"
        mock_entry_points.return_value = [mock_ep]

        discovered = self.registry.discover()
        self.assertIn("mock_provider", discovered)

    @patch("src.security_harness.plugins.registry.entry_points")
    def test_load_plugin_success(self, mock_entry_points):
        mock_ep = MagicMock()
        mock_ep.name = "mock_provider"
        mock_ep.load.return_value = MockCustomPlugin
        mock_entry_points.return_value = [mock_ep]

        plugin = self.registry.load_plugin("mock_provider")
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.metadata.name, "mock_provider")

    def test_load_nonexistent_plugin(self):
        plugin = self.registry.load_plugin("non_existent_provider_xyz")
        self.assertIsNone(plugin)

    @patch("src.security_harness.plugins.registry.entry_points")
    def test_build_adapter_with_plugin_fallback(self, mock_entry_points):
        mock_ep = MagicMock()
        mock_ep.name = "mock_provider"
        mock_ep.load.return_value = MockCustomPlugin
        mock_entry_points.return_value = [mock_ep]

        adapter = build_adapter("mock_provider")
        self.assertEqual(adapter.provider_name, "mock_provider")

    def test_build_adapter_unknown_provider_raises(self):
        with self.assertRaises(ConfigurationError):
            build_adapter("invalid_provider_12345")
