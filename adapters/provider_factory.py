"""
Provider factory — instantiate adapters from configuration.

Usage:
    adapter = build_adapter("openai")
    adapter = build_adapter("anthropic")
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import yaml

from adapters.base_adapter import ProviderAdapter
from security_harness.errors import ConfigurationError

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

# Registry: provider name → adapter class (lazy imports to avoid loading all SDKs)
_ADAPTER_CLASSES: dict[str, str] = {
    "openai": "adapters.openai_adapter.OpenAIAdapter",
    "anthropic": "adapters.anthropic_adapter.AnthropicAdapter",
    "google": "adapters.gemini_adapter.GeminiAdapter",
    "xai": "adapters.xai_adapter.XAIAdapter",
}


def _import_class(dotted_path: str) -> type:
    """Import a class from a dotted module path string."""
    module_path, class_name = dotted_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def build_adapter(
    provider: str,
    api_key: str | None = None,
    retry_config: dict | None = None,
) -> ProviderAdapter:
    """
    Instantiate and return a provider adapter.

    Args:
        provider:     Provider name matching providers.yaml (e.g., "openai").
        api_key:      Optional override; if None, loaded from environment.
        retry_config: Optional override for retry settings.

    Returns:
        A configured ProviderAdapter instance.

    Raises:
        ConfigurationError: If the provider name is not registered.
    """
    dotted_path = _ADAPTER_CLASSES.get(provider)
    if dotted_path is None:
        raise ConfigurationError(
            f"Unknown provider {provider!r}. "
            f"Registered providers: {list(_ADAPTER_CLASSES)}"
        )

    cls = _import_class(dotted_path)
    adapter = cls(api_key=api_key, retry_config=retry_config)
    log.info("provider_factory.built", extra={"provider": provider})
    return adapter  # type: ignore[return-value]


def build_all_adapters(
    providers: list[str] | None = None,
    retry_config: dict | None = None,
) -> dict[str, ProviderAdapter]:
    """
    Build adapters for all (or a subset of) registered providers.

    Providers whose API keys are not set in the environment are skipped
    with a warning rather than raising an error.

    Args:
        providers: Explicit list of provider names. Defaults to all registered.
        retry_config: Optional shared retry config.

    Returns:
        Dict mapping provider name → adapter.
    """
    from adapters.auth import has_api_key

    target_providers = providers or list(_ADAPTER_CLASSES)
    adapters: dict[str, ProviderAdapter] = {}

    for provider in target_providers:
        # Load providers.yaml to find the env key
        env_key = _get_env_key(provider)
        if env_key and not has_api_key(env_key):
            log.warning(
                "provider_factory.skipped",
                extra={
                    "provider": provider,
                    "reason": f"{env_key} not set",
                },
            )
            continue
        try:
            adapters[provider] = build_adapter(provider, retry_config=retry_config)
        except Exception as exc:
            log.error(
                "provider_factory.build_failed",
                extra={"provider": provider, "error": str(exc)},
            )

    return adapters


def _get_env_key(provider: str) -> str | None:
    """Return the environment variable name for a provider's API key."""
    try:
        with open("config/providers.yaml") as f:
            config = yaml.safe_load(f) or {}
        return config.get(provider, {}).get("env_key")
    except FileNotFoundError:
        return None
