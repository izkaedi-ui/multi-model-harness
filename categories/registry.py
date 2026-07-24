"""
Category registry — discovers and manages all installed evaluation categories.
"""

from __future__ import annotations

import importlib
import logging

from categories.base import BaseCategory

log = logging.getLogger(__name__)

_CATEGORY_MODULE_PATHS = {
    "guardrail_consistency": "categories.guardrail_consistency.category.GuardrailConsistencyCategory",
    "tool_use_boundaries": "categories.tool_use_boundaries.category.ToolUseBoundariesCategory",
    "prompt_robustness": "categories.prompt_robustness.category.PromptRobustnessCategory",
    "context_isolation": "categories.context_isolation.category.ContextIsolationCategory",
    "long_context_behavior": "categories.long_context_behavior.category.LongContextBehaviorCategory",
    "content_integrity": "categories.content_integrity.category.ContentIntegrityCategory",
}


class CategoryRegistry:
    """
    Registry for all evaluation categories.

    Usage:
        registry = CategoryRegistry.default()
        guardrail = registry.get("guardrail_consistency")
        for case in guardrail.load_cases():
            ...
    """

    def __init__(self, categories: dict[str, BaseCategory]) -> None:
        self._categories = categories

    @classmethod
    def default(cls) -> CategoryRegistry:
        """Load all built-in categories."""
        categories: dict[str, BaseCategory] = {}
        for name, dotted_path in _CATEGORY_MODULE_PATHS.items():
            try:
                module_path, class_name = dotted_path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                klass = getattr(module, class_name)
                categories[name] = klass()
                log.debug("registry.loaded", extra={"category": name})
            except Exception as exc:
                log.error(
                    "registry.load_failed",
                    extra={"category": name, "error": str(exc)},
                )
        return cls(categories)

    def get(self, name: str) -> BaseCategory:
        if name not in self._categories:
            raise KeyError(f"Unknown category {name!r}. Available: {list(self._categories)}")
        return self._categories[name]

    def all(self) -> list[BaseCategory]:
        return list(self._categories.values())

    def names(self) -> list[str]:
        return list(self._categories)
