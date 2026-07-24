"""
Unit tests for Stage 3B Statistical Engine & Bootstrap Analysis.
"""
from __future__ import annotations

import unittest
from analytics.statistics import StatisticalEngine, ConfidenceInterval
from security_harness.errors import ConfigurationError


class TestStatisticalEngine(unittest.TestCase):
    def test_summary_calculation(self):
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        stats = StatisticalEngine.calculate_summary(vals)
        self.assertEqual(stats["mean"], 3.0)
        self.assertEqual(stats["median"], 3.0)
        self.assertAlmostEqual(stats["variance"], 2.5)

    def test_empty_sample_raises(self):
        with self.assertRaises(ConfigurationError):
            StatisticalEngine.calculate_summary([])

    def test_reproducible_bootstrap_ci(self):
        vals = [0.8, 0.85, 0.9, 0.95, 0.7, 0.75, 0.88, 0.92, 0.81, 0.89]
        ci1 = StatisticalEngine.bootstrap_ci(vals, confidence=0.95, iterations=500, seed=123)
        ci2 = StatisticalEngine.bootstrap_ci(vals, confidence=0.95, iterations=500, seed=123)
        
        self.assertEqual(ci1.mean, ci2.mean)
        self.assertEqual(ci1.ci_lower, ci2.ci_lower)
        self.assertEqual(ci1.ci_upper, ci2.ci_upper)
        self.assertTrue(ci1.ci_lower <= ci1.mean <= ci1.ci_upper)

    def test_small_sample_warning(self):
        vals = [1.0, 2.0]
        ci = StatisticalEngine.bootstrap_ci(vals)
        self.assertIn("Small sample size", ci.warning)

    def test_pairwise_delta_ci(self):
        sample_a = [0.9, 0.95, 0.88, 0.92]
        sample_b = [0.6, 0.65, 0.7, 0.58]
        delta_mean, ci_low, ci_high = StatisticalEngine.pairwise_delta_ci(sample_a, sample_b, seed=42)
        self.assertTrue(delta_mean > 0.2)
        self.assertTrue(ci_low <= delta_mean <= ci_high)
