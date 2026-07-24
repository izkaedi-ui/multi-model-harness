"""
Integration tests for Stage 3C Execution Manifests and Environment Replay / Drift Detection.
"""
from __future__ import annotations

import json
import unittest

from runner.manifest import ExecutionManifest
from runner.replay import ReplayEngine
from security_harness.errors import ConfigurationError


class TestExecutionReplayIntegration(unittest.TestCase):
    def setUp(self):
        self.manifest = ExecutionManifest.create(
            run_id="run_test_123",
            benchmark_id="scenario_prompt_inj",
            benchmark_version="1.0.0",
            benchmark_fingerprint="abc123sha256hash",
            providers=["openai", "anthropic"],
            models=["gpt-4o", "claude-sonnet-4-6"],
            parameters={"temperature": 0.0, "max_tokens": 100},
            seed=42,
        )

    def test_manifest_creation_and_serialization(self):
        json_str = self.manifest.to_json()
        data = json.loads(json_str)
        self.assertEqual(data["run_id"], "run_test_123")
        self.assertEqual(data["schema_version"], "1.0.0")
        self.assertEqual(data["benchmark_fingerprint"], "abc123sha256hash")

    def test_replay_no_drift(self):
        curr_env = {
            "git_commit": self.manifest.git_commit,
            "python_version": self.manifest.python_version,
            "benchmark_fingerprint": "abc123sha256hash",
            "config_hash": self.manifest.config_hash,
        }
        parsed_manifest, drift = ReplayEngine.replay_manifest(self.manifest.to_json(), curr_env, strict=True)
        self.assertEqual(len(drift), 0)
        self.assertEqual(parsed_manifest.run_id, "run_test_123")

    def test_replay_detects_git_and_fingerprint_drift(self):
        curr_env = {
            "git_commit": "different_commit_hash",
            "python_version": self.manifest.python_version,
            "benchmark_fingerprint": "different_fingerprint_hash",
            "config_hash": self.manifest.config_hash,
        }
        _, drift = ReplayEngine.replay_manifest(self.manifest.to_json(), curr_env, strict=False)
        self.assertEqual(len(drift), 2)
        self.assertTrue(any("Git Commit Drift" in d for d in drift))
        self.assertTrue(any("Benchmark Fingerprint Drift" in d for d in drift))

    def test_strict_replay_raises_on_drift(self):
        curr_env = {
            "git_commit": "different_commit_hash",
            "python_version": self.manifest.python_version,
        }
        with self.assertRaises(ConfigurationError):
            ReplayEngine.replay_manifest(self.manifest.to_json(), curr_env, strict=True)
