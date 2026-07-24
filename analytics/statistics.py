"""
Statistical Confidence & Bootstrap Analysis Engine for Stage 3B.
"""
from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass

from security_harness.errors import ConfigurationError


@dataclass(frozen=True)
class ConfidenceInterval:
    mean: float
    ci_lower: float
    ci_upper: float
    confidence_level: float
    sample_size: int
    std_dev: float
    warning: str = ""


class StatisticalEngine:
    """Calculates statistical summary metrics and reproducible bootstrap confidence intervals."""

    @staticmethod
    def calculate_summary(values: list[float]) -> dict[str, float]:
        """Compute basic summary statistics."""
        if not values:
            raise ConfigurationError("Cannot compute statistics on empty input")

        n = len(values)
        mean_val = statistics.mean(values)
        median_val = statistics.median(values)
        variance_val = statistics.variance(values) if n > 1 else 0.0
        std_dev_val = math.sqrt(variance_val)

        return {
            "count": float(n),
            "mean": mean_val,
            "median": median_val,
            "variance": variance_val,
            "std_dev": std_dev_val,
        }

    @classmethod
    def bootstrap_ci(
        cls,
        values: list[float],
        confidence: float = 0.95,
        iterations: int = 1000,
        seed: int = 42,
    ) -> ConfidenceInterval:
        """Compute reproducible bootstrap confidence intervals."""
        if not values:
            raise ConfigurationError("Cannot compute bootstrap CI on empty input")

        n = len(values)
        warning = ""
        if n < 10:
            warning = f"Small sample size ({n} < 10); confidence intervals may be wide or unstable."

        if n == 1:
            val = values[0]
            return ConfidenceInterval(
                mean=val,
                ci_lower=val,
                ci_upper=val,
                confidence_level=confidence,
                sample_size=1,
                std_dev=0.0,
                warning=warning,
            )

        rng = random.Random(seed)
        means: list[float] = []

        for _ in range(iterations):
            resample = [rng.choice(values) for _ in range(n)]
            means.append(statistics.mean(resample))

        means.sort()
        alpha = 1.0 - confidence
        lower_idx = int((alpha / 2.0) * iterations)
        upper_idx = int((1.0 - alpha / 2.0) * iterations)
        upper_idx = min(upper_idx, iterations - 1)

        summary = cls.calculate_summary(values)
        return ConfidenceInterval(
            mean=summary["mean"],
            ci_lower=means[lower_idx],
            ci_upper=means[upper_idx],
            confidence_level=confidence,
            sample_size=n,
            std_dev=summary["std_dev"],
            warning=warning,
        )

    @classmethod
    def pairwise_delta_ci(
        cls,
        sample_a: list[float],
        sample_b: list[float],
        confidence: float = 0.95,
        iterations: int = 1000,
        seed: int = 42,
    ) -> tuple[float, float, float]:
        """Compute bootstrap CI for difference in means (mean_a - mean_b)."""
        if not sample_a or not sample_b:
            raise ConfigurationError("Samples for pairwise comparison cannot be empty")

        rng = random.Random(seed)
        deltas: list[float] = []
        n_a, n_b = len(sample_a), len(sample_b)

        for _ in range(iterations):
            res_a = [rng.choice(sample_a) for _ in range(n_a)]
            res_b = [rng.choice(sample_b) for _ in range(n_b)]
            deltas.append(statistics.mean(res_a) - statistics.mean(res_b))

        deltas.sort()
        alpha = 1.0 - confidence
        lower_idx = int((alpha / 2.0) * iterations)
        upper_idx = min(int((1.0 - alpha / 2.0) * iterations), iterations - 1)

        delta_mean = statistics.mean(sample_a) - statistics.mean(sample_b)
        return delta_mean, deltas[lower_idx], deltas[upper_idx]
