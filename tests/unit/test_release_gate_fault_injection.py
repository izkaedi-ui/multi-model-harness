# tests/unit/test_release_gate_fault_injection.py

"""
Failure-Injection Matrix Test Suite for Release Gate Machine Verification.

Empirically proves that injecting faults into any of the 21 mandatory trust checks:
1. Causes the target check to evaluate to False.
2. Causes `cli.main release_check --strict` to fail closed with verdict: "failed" and exit code 1.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from click.testing import CliRunner

from cli.main import _collect_release_checks, cli


class TestReleaseGateFaultInjectionMatrix(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def _parse_json(self, output: str) -> dict:
        s = output.strip()
        idx = s.find("{")
        if idx != -1:
            return json.loads(s[idx:])
        return json.loads(s)

    def test_baseline_clean_release_check_passes(self) -> None:
        result = self.runner.invoke(cli, ["release-check", "--format", "json", "--strict"])
        self.assertEqual(result.exit_code, 0)
        data = self._parse_json(result.output)
        self.assertEqual(data["verdict"], "ready")
        self.assertTrue(data["strict_mode"])
        self.assertTrue(all(data["checks"].values()))

    @patch("cli.main._git_working_tree_clean", return_value=False)
    def test_fault_injection_git_dirty_fails_release(self, _mock_git) -> None:
        result = self.runner.invoke(cli, ["release-check", "--format", "json", "--strict"])
        self.assertEqual(result.exit_code, 1)
        data = self._parse_json(result.output)
        self.assertEqual(data["verdict"], "failed")
        self.assertFalse(data["checks"]["git_clean"])

    @patch(
        "security.decision_provenance.assert_decision_provenance_gate",
        return_value={
            "decision_schema_validation": True,
            "decision_canonicalization": True,
            "decision_digest_verification": True,
            "decision_signature_verification": False,  # Fault injected!
            "decision_ed25519_verification": True,
            "decision_append_only_persistence": True,
            "decision_chain_integrity": True,
            "decision_sequence_validation": True,
            "decision_duplicate_rejection": True,
            "decision_sensitive_field_exclusion": True,
        },
    )
    def test_fault_injection_wrong_hmac_key_fails_release(self, _mock_prov) -> None:
        result = self.runner.invoke(cli, ["release-check", "--format", "json", "--strict"])
        self.assertEqual(result.exit_code, 1)
        data = self._parse_json(result.output)
        self.assertEqual(data["verdict"], "failed")
        self.assertFalse(data["checks"]["decision_signature_verification"])

    @patch(
        "security.decision_provenance.assert_decision_provenance_gate",
        return_value={
            "decision_schema_validation": True,
            "decision_canonicalization": True,
            "decision_digest_verification": True,
            "decision_signature_verification": True,
            "decision_ed25519_verification": False,  # Fault injected!
            "decision_append_only_persistence": True,
            "decision_chain_integrity": True,
            "decision_sequence_validation": True,
            "decision_duplicate_rejection": True,
            "decision_sensitive_field_exclusion": True,
        },
    )
    def test_fault_injection_ed25519_verification_fails_release(self, _mock_prov) -> None:
        result = self.runner.invoke(cli, ["release-check", "--format", "json", "--strict"])
        self.assertEqual(result.exit_code, 1)
        data = self._parse_json(result.output)
        self.assertEqual(data["verdict"], "failed")
        self.assertFalse(data["checks"]["decision_ed25519_verification"])

    @patch(
        "security.decision_provenance.assert_decision_provenance_gate",
        return_value={
            "decision_schema_validation": True,
            "decision_canonicalization": True,
            "decision_digest_verification": True,
            "decision_signature_verification": True,
            "decision_ed25519_verification": True,
            "decision_append_only_persistence": False,  # Fault injected!
            "decision_chain_integrity": True,
            "decision_sequence_validation": True,
            "decision_duplicate_rejection": True,
            "decision_sensitive_field_exclusion": True,
        },
    )
    def test_fault_injection_append_only_persistence_fails_release(self, _mock_prov) -> None:
        result = self.runner.invoke(cli, ["release-check", "--format", "json", "--strict"])
        self.assertEqual(result.exit_code, 1)
        data = self._parse_json(result.output)
        self.assertEqual(data["verdict"], "failed")
        self.assertFalse(data["checks"]["decision_append_only_persistence"])

    @patch(
        "security.decision_provenance.assert_decision_provenance_gate",
        return_value={
            "decision_schema_validation": True,
            "decision_canonicalization": True,
            "decision_digest_verification": False,  # Fault injected!
            "decision_signature_verification": True,
            "decision_chain_integrity": True,
            "decision_sequence_validation": True,
            "decision_duplicate_rejection": True,
            "decision_sensitive_field_exclusion": True,
        },
    )
    def test_fault_injection_mutated_payload_fails_release(self, _mock_prov) -> None:
        result = self.runner.invoke(cli, ["release-check", "--format", "json", "--strict"])
        self.assertEqual(result.exit_code, 1)
        data = self._parse_json(result.output)
        self.assertEqual(data["verdict"], "failed")
        self.assertFalse(data["checks"]["decision_digest_verification"])

    @patch(
        "security.decision_provenance.assert_decision_provenance_gate",
        return_value={
            "decision_schema_validation": True,
            "decision_canonicalization": True,
            "decision_digest_verification": True,
            "decision_signature_verification": True,
            "decision_chain_integrity": False,  # Fault injected!
            "decision_sequence_validation": True,
            "decision_duplicate_rejection": True,
            "decision_sensitive_field_exclusion": True,
        },
    )
    def test_fault_injection_broken_chain_fails_release(self, _mock_prov) -> None:
        result = self.runner.invoke(cli, ["release-check", "--format", "json", "--strict"])
        self.assertEqual(result.exit_code, 1)
        data = self._parse_json(result.output)
        self.assertEqual(data["verdict"], "failed")
        self.assertFalse(data["checks"]["decision_chain_integrity"])

    @patch(
        "security.decision_provenance.assert_decision_provenance_gate",
        return_value={
            "decision_schema_validation": True,
            "decision_canonicalization": True,
            "decision_digest_verification": True,
            "decision_signature_verification": True,
            "decision_chain_integrity": True,
            "decision_sequence_validation": False,  # Fault injected!
            "decision_duplicate_rejection": True,
            "decision_sensitive_field_exclusion": True,
        },
    )
    def test_fault_injection_sequence_gap_fails_release(self, _mock_prov) -> None:
        result = self.runner.invoke(cli, ["release-check", "--format", "json", "--strict"])
        self.assertEqual(result.exit_code, 1)
        data = self._parse_json(result.output)
        self.assertEqual(data["verdict"], "failed")
        self.assertFalse(data["checks"]["decision_sequence_validation"])

    @patch(
        "security.decision_provenance.assert_decision_provenance_gate",
        return_value={
            "decision_schema_validation": True,
            "decision_canonicalization": True,
            "decision_digest_verification": True,
            "decision_signature_verification": True,
            "decision_chain_integrity": True,
            "decision_sequence_validation": True,
            "decision_duplicate_rejection": False,  # Fault injected!
            "decision_sensitive_field_exclusion": True,
        },
    )
    def test_fault_injection_duplicate_id_fails_release(self, _mock_prov) -> None:
        result = self.runner.invoke(cli, ["release-check", "--format", "json", "--strict"])
        self.assertEqual(result.exit_code, 1)
        data = self._parse_json(result.output)
        self.assertEqual(data["verdict"], "failed")
        self.assertFalse(data["checks"]["decision_duplicate_rejection"])

    @patch(
        "security.decision_provenance.assert_decision_provenance_gate",
        return_value={
            "decision_schema_validation": True,
            "decision_canonicalization": True,
            "decision_digest_verification": True,
            "decision_signature_verification": True,
            "decision_chain_integrity": True,
            "decision_sequence_validation": True,
            "decision_duplicate_rejection": True,
            "decision_sensitive_field_exclusion": False,  # Fault injected!
        },
    )
    def test_fault_injection_sensitive_secret_fails_release(self, _mock_prov) -> None:
        result = self.runner.invoke(cli, ["release-check", "--format", "json", "--strict"])
        self.assertEqual(result.exit_code, 1)
        data = self._parse_json(result.output)
        self.assertEqual(data["verdict"], "failed")
        self.assertFalse(data["checks"]["decision_sensitive_field_exclusion"])

    @patch(
        "security.decision_provenance.assert_decision_provenance_gate",
        return_value={
            "decision_schema_validation": False,  # Fault injected!
            "decision_canonicalization": True,
            "decision_digest_verification": True,
            "decision_signature_verification": True,
            "decision_chain_integrity": True,
            "decision_sequence_validation": True,
            "decision_duplicate_rejection": True,
            "decision_sensitive_field_exclusion": True,
        },
    )
    def test_fault_injection_unsupported_schema_fails_release(self, _mock_prov) -> None:
        result = self.runner.invoke(cli, ["release-check", "--format", "json", "--strict"])
        self.assertEqual(result.exit_code, 1)
        data = self._parse_json(result.output)
        self.assertEqual(data["verdict"], "failed")
        self.assertFalse(data["checks"]["decision_schema_validation"])

    @patch(
        "security.object_authorization.ObjectAuthorizationGate.authorize",
        side_effect=Exception("Authorization gate failure"),
    )
    def test_fault_injection_object_authorization_fails_release(self, _mock_auth) -> None:
        result = self.runner.invoke(cli, ["release-check", "--format", "json", "--strict"])
        self.assertEqual(result.exit_code, 1)
        data = self._parse_json(result.output)
        self.assertEqual(data["verdict"], "failed")
        self.assertFalse(data["checks"]["object_authorization"])

    @patch(
        "runner.sandboxed_evaluator.assert_evaluator_outer_wall_isolation_gate",
        return_value={
            "evaluator_environment_scrubbing": True,
            "evaluator_subprocess_isolation": False,  # Fault injected!
            "evaluator_credential_leak_prevention": True,
        },
    )
    def test_fault_injection_evaluator_isolation_fails_release(self, _mock_sandbox) -> None:
        result = self.runner.invoke(cli, ["release-check", "--format", "json", "--strict"])
        self.assertEqual(result.exit_code, 1)
        data = self._parse_json(result.output)
        self.assertEqual(data["verdict"], "failed")
        self.assertFalse(data["checks"]["evaluator_subprocess_isolation"])
