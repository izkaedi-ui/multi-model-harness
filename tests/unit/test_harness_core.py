"""
Unit tests for the security test harness.
"""
import unittest
from adapters.cost_estimator import estimate_cost_usd
from runner.cost_guard import CostGuard
from security.secret_redactor import SecretRedactor
from security_harness.errors import BudgetExceeded

class TestHarnessCore(unittest.TestCase):
    def test_estimate_cost_usd_positive(self):
        cost = estimate_cost_usd("gpt-4o", 1000, 500)
        self.assertTrue(cost > 0.0)

    def test_estimate_cost_usd_unknown(self):
        cost = estimate_cost_usd("unknown-model", 1000, 500)
        self.assertEqual(cost, 0.0)

    def test_budget_enforcement(self):
        guard = CostGuard(global_cap_usd=10.0, reserve_usd=2.0, provider_caps={"openai": 5.0})
        guard.check_provider("openai", 1.0)
        with self.assertRaises(BudgetExceeded):
            guard.check_provider("openai", 6.0)

    def test_redact_string(self):
        redactor = SecretRedactor.default()
        raw = "My key is sk-proj-123456789012345678901234"
        clean = redactor.redact_string(raw)
        self.assertNotIn("sk-proj-123456789012345678901234", clean)

if __name__ == "__main__":
    unittest.main()
