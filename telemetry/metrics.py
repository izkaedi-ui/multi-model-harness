# telemetry/metrics.py

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter

ALLOWED_STATUSES = frozenset(
    {
        "success",
        "failed",
        "errored",
        "timeout",
        "cancelled",
    }
)


@dataclass(slots=True)
class MetricsRuntime:
    requests: object | None = None
    latency: object | None = None
    retries: object | None = None
    tokens: object | None = None
    cost: object | None = None
    active: object | None = None

    def record_request(
        self,
        *,
        provider: str,
        model: str,
        status: str,
    ) -> None:
        if self.requests is None:
            return

        safe_status = (
            status if status in ALLOWED_STATUSES else "errored"
        )

        self.requests.labels(
            provider=provider,
            model=model,
            status=safe_status,
        ).inc()

    def record_retry(
        self,
        *,
        provider: str,
        model: str,
        reason: str,
    ) -> None:
        if self.retries is None:
            return

        safe_reason = reason if reason in {
            "rate_limit",
            "connection",
            "timeout",
            "server_error",
        } else "other"

        self.retries.labels(
            provider=provider,
            model=model,
            reason=safe_reason,
        ).inc()

    def record_usage(
        self,
        *,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> None:
        labels = {"provider": provider, "model": model}

        if self.tokens is not None:
            self.tokens.labels(
                **labels,
                direction="input",
            ).inc(max(0, input_tokens))

            self.tokens.labels(
                **labels,
                direction="output",
            ).inc(max(0, output_tokens))

        if self.cost is not None:
            self.cost.labels(**labels).inc(max(0.0, cost_usd))

    @contextmanager
    def observe_latency(
        self,
        *,
        provider: str,
        model: str,
    ) -> Iterator[None]:
        started = perf_counter()

        if self.active is not None:
            self.active.inc()

        try:
            yield
        finally:
            elapsed = perf_counter() - started

            if self.latency is not None:
                self.latency.labels(
                    provider=provider,
                    model=model,
                ).observe(elapsed)

            if self.active is not None:
                self.active.dec()


def build_prometheus_metrics() -> MetricsRuntime:
    try:
        from prometheus_client import Counter, Gauge, Histogram
    except ImportError:
        return MetricsRuntime()

    return MetricsRuntime(
        requests=Counter(
            "harness_requests_total",
            "Total provider requests.",
            ("provider", "model", "status"),
        ),
        latency=Histogram(
            "harness_request_latency_seconds",
            "Provider request latency.",
            ("provider", "model"),
            buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 60),
        ),
        retries=Counter(
            "harness_retries_total",
            "Total provider retries.",
            ("provider", "model", "reason"),
        ),
        tokens=Counter(
            "harness_tokens_total",
            "Input and output token usage.",
            ("provider", "model", "direction"),
        ),
        cost=Counter(
            "harness_cost_usd_total",
            "Estimated provider cost.",
            ("provider", "model"),
        ),
        active=Gauge(
            "harness_active_executions",
            "Currently active executions.",
        ),
    )
