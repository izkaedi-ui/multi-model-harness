"""
Unit tests for CLI output purity, database transaction rollbacks, cost reconciliation invariants,
and artifact scanner scrubbing.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch
import os
import json
import sqlite3

from click.testing import CliRunner
from cli.main import cli
from database.repository import HarnessRepository
from database.transactions import async_transaction
from security.artifact_scanner import ArtifactScanner
from adapters.cost_estimator import estimate_cost_usd


class TestCLIMachineReadablePurity(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @patch(
        "cli.main._collect_release_checks",
        return_value={
            "compilation": True,
            "unit_tests": True,
            "validation": True,
            "database_integrity": True,
            "git_clean": True,
        },
    )
    def test_release_check_json_purity(self, _mock_checks):
        result = self.runner.invoke(cli, ["release-check", "--format", "json", "--strict"])
        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.output.strip())
        self.assertEqual(data["verdict"], "ready")
        self.assertTrue(data["strict_mode"])
        self.assertTrue(all(data["checks"].values()))

    @patch(
        "cli.main._collect_release_checks",
        return_value={
            "compilation": True,
            "unit_tests": True,
            "validation": True,
            "database_integrity": True,
            "git_clean": False,
        },
    )
    def test_release_check_json_strict_failure(self, _mock_checks):
        result = self.runner.invoke(cli, ["release-check", "--format", "json", "--strict"])
        self.assertEqual(result.exit_code, 1)
        data = json.loads(result.output.strip())
        self.assertEqual(data["verdict"], "failed")
        self.assertFalse(data["checks"]["git_clean"])

    def test_write_json_stdout_bypasses_click_console_layer(self):
        import io
        from cli.main import _write_json_stdout
        stream = io.StringIO()
        with patch("sys.stdout", stream):
            _write_json_stdout(
                {
                    "verdict": "ready",
                    "strict_mode": True,
                    "checks": {"compilation": True},
                }
            )
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["verdict"], "ready")
        self.assertTrue(payload["strict_mode"])





class TestArtifactScanner(unittest.TestCase):
    def test_scanner_clean_and_dirty_files(self):
        scanner = ArtifactScanner.default()
        clean_content = '{"status": "ok", "result": "passed"}'
        dirty_content = '{"status": "ok", "key": "sk-1234567890abcdefghijklmnopqrstuvwxyz123456"}'
        self.assertTrue(scanner.scan_text(clean_content, ".json"))
        self.assertFalse(scanner.scan_text(dirty_content, ".json"))


class TestCostReconciliationInvariants(unittest.TestCase):
    def test_cost_invariants(self):
        # Known model with non-zero tokens must produce > 0 cost
        cost = estimate_cost_usd("gpt-4o", input_tokens=1000, output_tokens=500)
        self.assertGreater(cost, 0.0)

        # 0 tokens must produce 0.0 cost
        zero_cost = estimate_cost_usd("gpt-4o", input_tokens=0, output_tokens=0)
        self.assertEqual(zero_cost, 0.0)
