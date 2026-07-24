"""
Unit tests for Stage 3A Evaluator Contracts & JudgeEnsemble.
"""
from __future__ import annotations

import unittest
from evaluators.contracts import EvaluatorResult, EnsembleVerdict
from evaluators.ensemble import JudgeEnsemble
from security_harness.errors import ConfigurationError


class TestJudgeEnsemble(unittest.TestCase):
    def setUp(self):
        self.j1 = EvaluatorResult(judge_id="judge_1", passed=True, score=1.0)
        self.j2 = EvaluatorResult(judge_id="judge_2", passed=True, score=0.8)
        self.j3 = EvaluatorResult(judge_id="judge_3", passed=False, score=0.2)

    def test_weighted_majority_pass(self):
        ensemble = JudgeEnsemble(strategy="weighted_majority")
        verdict = ensemble.consolidate([self.j1, self.j2, self.j3])
        self.assertTrue(verdict.passed)
        self.assertTrue(verdict.disagreement_reported)
        self.assertAlmostEqual(verdict.agreement_ratio, 2.0 / 3.0)

    def test_unanimous_consensus_failure(self):
        ensemble = JudgeEnsemble(strategy="consensus")
        verdict = ensemble.consolidate([self.j1, self.j2, self.j3])
        self.assertFalse(verdict.passed)

    def test_deterministic_tie_breaker(self):
        j_pass = EvaluatorResult(judge_id="j1", passed=True, score=0.6)
        j_fail = EvaluatorResult(judge_id="j2", passed=False, score=0.4)
        ensemble = JudgeEnsemble(strategy="weighted_majority")
        verdict = ensemble.consolidate([j_pass, j_fail])
        self.assertTrue(verdict.passed)
        self.assertTrue(verdict.tie_broken)

    def test_invalid_negative_weight_raises(self):
        ensemble = JudgeEnsemble(weights={"judge_1": -1.0})
        with self.assertRaises(ConfigurationError):
            ensemble.consolidate([self.j1])

    def test_empty_results_fail_closed(self):
        ensemble = JudgeEnsemble(missing_judge_policy="fail_closed")
        verdict = ensemble.consolidate([])
        self.assertFalse(verdict.passed)
