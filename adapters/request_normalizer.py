"""
Request normaliser — converts TestCase + model config into a ModelRequest.
"""

from __future__ import annotations

import logging

import yaml

from security_harness.types import ModelRequest, TestCase

log = logging.getLogger(__name__)

_MODELS_CACHE: dict | None = None


def _load_models(config_path: str = "config/models.yaml") -> dict:
    global _MODELS_CACHE
    if _MODELS_CACHE is None:
        try:
            with open(config_path) as f:
                _MODELS_CACHE = yaml.safe_load(f) or {}
        except FileNotFoundError:
            _MODELS_CACHE = {}
    return _MODELS_CACHE


def normalise_request(
    test_case: TestCase,
    model: str,
    system_prompt: str | None = None,
    tools: list[dict] | None = None,
) -> ModelRequest:
    """
    Build a normalised ModelRequest from a TestCase and model identifier.

    Model defaults (temperature, max_output_tokens) are loaded from models.yaml
    and can be overridden per call.

    Args:
        test_case:     The test case to run.
        model:         Full model identifier (e.g., "gpt-4o").
        system_prompt: Optional system prompt override.
        tools:         Optional tool definitions (JSON schema format).

    Returns:
        A frozen ModelRequest ready for adapter dispatch.
    """
    models = _load_models()

    # Find model config across all providers
    model_config: dict = {}
    for _provider_models in models.values():
        if model in _provider_models:
            model_config = _provider_models[model]
            break

    temperature = model_config.get("default_temperature", 0.0)
    max_output_tokens = model_config.get("max_output_tokens", 800)

    messages = tuple(test_case.messages)

    return ModelRequest(
        model=model,
        messages=messages,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        tools=tuple(tools) if tools else None,
        system_prompt=system_prompt,
        metadata={
            "test_case_id": test_case.id,
            "category": test_case.category,
            "subcategory": test_case.subcategory,
        },
    )
