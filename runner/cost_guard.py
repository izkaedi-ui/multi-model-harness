"""
Cost guard — real-time budget enforcement.

Raises BudgetExceeded BEFORE a request is dispatched if it would cause any cap to
be exceeded. The request is never sent, so there is no overspend.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from security_harness.errors import BudgetExceeded, GlobalBudgetExceeded

log = logging.getLogger(__name__)


@dataclass
class CostGuard:
    """Tracks spend and enforces per-provider and global caps."""

    global_cap_usd: float
    reserve_usd: float
    provider_caps: dict[str, float]
    _provider_spend: dict[str, float] = field(default_factory=dict)
    _global_spend: float = field(default=0.0)

    @classmethod
    def from_config(cls, config: dict) -> CostGuard:
        global_cfg = config.get("global", {})
        provider_cfg = config.get("providers", {})

        return cls(
            global_cap_usd=global_cfg.get("maximum_total_usd", 35.0),
            reserve_usd=global_cfg.get("reserve_usd", 5.0),
            provider_caps={
                name: settings.get("maximum_usd", 8.0)
                for name, settings in provider_cfg.items()
            },
        )

    @property
    def effective_global_cap(self) -> float:
        return self.global_cap_usd - self.reserve_usd

    def check_provider(self, provider: str, estimated_cost_usd: float) -> None:
        """
        Verify that the estimated cost can be absorbed without exceeding any cap.

        Raises BudgetExceeded or GlobalBudgetExceeded before the request is sent.
        """
        current_provider = self._provider_spend.get(provider, 0.0)
        provider_cap = self.provider_caps.get(provider, float("inf"))

        if current_provider + estimated_cost_usd > provider_cap:
            raise BudgetExceeded(
                provider=provider,
                estimated_cost_usd=estimated_cost_usd,
                cap_usd=provider_cap,
                current_spend_usd=current_provider,
            )

        if self._global_spend + estimated_cost_usd > self.effective_global_cap:
            raise GlobalBudgetExceeded(
                provider="global",
                estimated_cost_usd=estimated_cost_usd,
                cap_usd=self.effective_global_cap,
                current_spend_usd=self._global_spend,
            )

    def record_spend(self, provider: str, actual_cost_usd: float) -> None:
        """Call this after a successful request to update tracked spend."""
        self._provider_spend[provider] = self._provider_spend.get(provider, 0.0) + actual_cost_usd
        self._global_spend += actual_cost_usd
        log.info("cost_guard.spend_recorded", extra={
            "provider": provider,
            "request_usd": actual_cost_usd,
            "provider_total_usd": self._provider_spend[provider],
            "global_total_usd": self._global_spend,
        })

    @property
    def total_cost_usd(self) -> float:
        return self._global_spend

    def summary(self) -> dict:
        return {
            "global_spend_usd": round(self._global_spend, 6),
            "global_cap_usd": self.effective_global_cap,
            "provider_spend": {k: round(v, 6) for k, v in self._provider_spend.items()},
            "provider_caps": self.provider_caps,
        }
