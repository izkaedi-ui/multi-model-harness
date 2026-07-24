"""
Replay and Environment Drift Detection Engine for Stage 3C.
"""
from __future__ import annotations

import json
from typing import Any

from runner.manifest import ExecutionManifest
from security_harness.errors import ConfigurationError


class ReplayEngine:
    """Validates execution manifests against current environment to detect configuration drift."""

    @staticmethod
    def detect_drift(manifest: ExecutionManifest, current_environment: dict[str, Any]) -> list[str]:
        """Compare manifest state with current environment and return list of detected drift warnings."""
        drift_warnings: list[str] = []

        if manifest.git_commit != "unknown" and current_environment.get("git_commit") != manifest.git_commit:
            drift_warnings.append(
                f"Git Commit Drift: Manifest commit {manifest.git_commit[:8]} != Current {current_environment.get('git_commit', 'unknown')[:8]}"
            )

        if manifest.python_version != current_environment.get("python_version"):
            drift_warnings.append(
                f"Python Version Drift: Manifest {manifest.python_version} != Current {current_environment.get('python_version')}"
            )

        if manifest.benchmark_fingerprint and current_environment.get("benchmark_fingerprint") != manifest.benchmark_fingerprint:
            drift_warnings.append(
                f"Benchmark Fingerprint Drift: Content hash mismatch for benchmark '{manifest.benchmark_id}'"
            )

        current_config_hash = current_environment.get("config_hash")
        if current_config_hash and current_config_hash != manifest.config_hash:
            drift_warnings.append(
                "Configuration Drift: Run parameters hash mismatch"
            )

        return drift_warnings

    @classmethod
    def replay_manifest(
        cls,
        manifest_json: str,
        current_environment: dict[str, Any],
        strict: bool = False,
    ) -> tuple[ExecutionManifest, list[str]]:
        """Parse manifest and verify whether it can be replayed safely."""
        data = json.loads(manifest_json)
        manifest = ExecutionManifest(**data)
        drift = cls.detect_drift(manifest, current_environment)

        if strict and drift:
            raise ConfigurationError("Strict replay failure due to detected environment drift:\n- " + "\n- ".join(drift))

        return manifest, drift
