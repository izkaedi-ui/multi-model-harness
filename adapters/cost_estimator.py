"""
Cost estimator — pre-flight cost calculation before dispatching requests.

Uses pricing metadata from models.yaml to estimate the cost of a request
based on the input token count. Output token count is estimated from max_output_tokens.
"""

from __future__ import annotations

import logging

import yaml

log = logging.getLogger(__name__)

_PRICING_CACHE: dict[str, dict] | None = None


def _load_pricing(config_path: str = "config/models.yaml") -> dict[str, dict]:
    global _PRICING_CACHE
    if _PRICING_CACHE is None:
        try:
            with open(config_path) as f:
                raw = yaml.safe_load(f) or {}
            # Flatten: {model_name: pricing_dict}
            pricing: dict[str, dict] = {}
            for _provider, models in raw.items():
                for model_name, meta in models.items():
                    pricing[model_name] = meta.get("pricing", {})
            _PRICING_CACHE = pricing
        except FileNotFoundError:
            log.warning("cost_estimator: models.yaml not found; estimates will be $0.00")
            _PRICING_CACHE = {}
    return _PRICING_CACHE


def estimate_cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """
    Estimate the cost in USD for a single request.

    Args:
        model:         Model identifier matching models.yaml.
        input_tokens:  Number of input tokens.
        output_tokens: Number of output tokens (use max_output_tokens for pre-flight estimate).

    Returns:
        Estimated cost in USD. Returns 0.0 if the model is not in models.yaml.
    """
    pricing = _load_pricing()
    model_pricing = pricing.get(model, {})
    if not model_pricing:
        # Longest-prefix matching (e.g. gpt-4o-mini-2024-07-18 matches gpt-4o-mini, not gpt-4o)
        matching_keys = sorted(
            [k for k in pricing.keys() if model.startswith(k)],
            key=len,
            reverse=True,
        )
        if matching_keys:
            model_pricing = pricing[matching_keys[0]]


    input_per_million = model_pricing.get("input_per_million", 0.0)
    output_per_million = model_pricing.get("output_per_million", 0.0)


    cost = (input_tokens / 1_000_000) * input_per_million + (
        output_tokens / 1_000_000
    ) * output_per_million

    return round(cost, 8)


def estimate_run_cost_usd(
    model: str,
    avg_input_tokens: int,
    max_output_tokens: int,
    num_cases: int,
    max_attempts: int = 1,
) -> float:
    """
    Estimate the total cost of a run before dispatch.

    Args:
        model:             Model identifier.
        avg_input_tokens:  Average input token count per case.
        max_output_tokens: Hard output cap from budgets.yaml.
        num_cases:         Number of test cases.
        max_attempts:      Maximum retry attempts per case (worst-case multiplier).

    Returns:
        Worst-case estimated cost in USD.
    """
    per_request = estimate_cost_usd(model, avg_input_tokens, max_output_tokens)
    total = per_request * num_cases * max_attempts
    log.debug(
        "cost_estimate",
        extra={
            "model": model,
            "num_cases": num_cases,
            "per_request_usd": per_request,
            "total_usd": total,
        },
    )
    return round(total, 6)
