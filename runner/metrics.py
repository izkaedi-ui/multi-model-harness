"""Run metrics — latency, throughput, error rates, token and cost tracking."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class RunMetrics:
    run_id: str
    _success_count: int = field(default=0)
    _error_count: int = field(default=0)
    _total_tokens: int = field(default=0)
    _total_cost_usd: float = field(default=0.0)
    _latencies_ms: list[int] = field(default_factory=list)
    _provider_errors: dict[str, int] = field(default_factory=dict)
    _started_at: float = field(default_factory=time.monotonic)

    def record_success(self, provider: str, latency_ms: int, tokens: int, cost_usd: float) -> None:
        self._success_count += 1
        self._latencies_ms.append(latency_ms)
        self._total_tokens += tokens
        self._total_cost_usd += cost_usd

    def record_error(self, provider: str, error_type: str) -> None:
        self._error_count += 1
        key = f"{provider}.{error_type}"
        self._provider_errors[key] = self._provider_errors.get(key, 0) + 1

    @property
    def total_cost_usd(self) -> float:
        return self._total_cost_usd

    @property
    def p50_latency_ms(self) -> float:
        if not self._latencies_ms: return 0.0
        s = sorted(self._latencies_ms)
        return s[len(s) // 2]

    @property
    def p95_latency_ms(self) -> float:
        if not self._latencies_ms: return 0.0
        s = sorted(self._latencies_ms)
        return s[int(len(s) * 0.95)]

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "success_count": self._success_count,
            "error_count": self._error_count,
            "total_tokens": self._total_tokens,
            "total_cost_usd": round(self._total_cost_usd, 6),
            "p50_latency_ms": self.p50_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "provider_errors": self._provider_errors,
        }
