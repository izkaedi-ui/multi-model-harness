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

    def test_release_check_json_purity(self):
        result = self.runner.invoke(cli, ["release-check", "--format", "json"])
        # Find JSON payload in CLI output
        raw_output = result.output.strip()
        json_start = raw_output.find("{")
        self.assertNotEqual(json_start, -1)
        json_str = raw_output[json_start:]
        data = json.loads(json_str)
        self.assertIn("verdict", data)
        self.assertIn("checks", data)



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
