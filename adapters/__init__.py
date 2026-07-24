"""
Adapters package — provider API clients.

All adapters implement the ProviderAdapter Protocol defined in base_adapter.py.
Instantiate adapters through provider_factory.py rather than directly.
"""

from adapters.base_adapter import BaseAdapter, ProviderAdapter
from adapters.provider_factory import build_adapter

__all__ = ["ProviderAdapter", "BaseAdapter", "build_adapter"]
