"""
Execution plan — builds the flat list of (test_case, model, adapter) tuples
that the runner will dispatch, filtered by model capabilities and budget.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adapters.base_adapter import ProviderAdapter
from adapters.capability_registry import CapabilityRegistry
from adapters.request_normalizer import normalise_request
from security_harness.correlation import generate_execution_id
from security_harness.types import ModelRequest, TestCase


@dataclass
class PlanItem:
    execution_id: str
    test_case: TestCase
    provider: str
    model: str
    adapter: ProviderAdapter
    request: ModelRequest


@dataclass
class ExecutionPlan:
    items: list[PlanItem]


def build_plan(
    test_cases: list[TestCase],
    adapters: dict[str, ProviderAdapter],
    cap_registry: CapabilityRegistry,
    config: Any,  # RunConfig
) -> ExecutionPlan:
    """
    Build the flat list of executions to run.

    For each (test_case, model) pair:
    - Skip if the model lacks required capabilities (e.g., tools).
    - Skip if the test case is tagged for a capability the model lacks.
    """
    items: list[PlanItem] = []

    for provider, adapter in adapters.items():
        models = cap_registry.models_for_provider(provider)
        if not models:
            continue

        for model_caps in models:
            model = model_caps.model

            for test_case in test_cases:
                # Skip tool-use tests for models that don't support tools
                if "tool-use" in test_case.tags and not model_caps.supports_tools:
                    continue

                request = normalise_request(test_case, model)

                items.append(
                    PlanItem(
                        execution_id=generate_execution_id(),
                        test_case=test_case,
                        provider=provider,
                        model=model,
                        adapter=adapter,
                        request=request,
                    )
                )

    return ExecutionPlan(items=items)
