"""
Execution Manifest Generator for Stage 3C Scientific Reproducibility.
"""
from __future__ import annotations

import os
import sys
import json
import hashlib
import platform
import subprocess
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any


@dataclass(frozen=True)
class ExecutionManifest:
    """Complete immutable execution environment snapshot for exact run replay."""
    schema_version: str = "1.0.0"
    run_id: str = ""
    git_commit: str = ""
    python_version: str = ""
    platform_info: str = ""
    config_hash: str = ""
    benchmark_id: str = ""
    benchmark_version: str = ""
    benchmark_fingerprint: str = ""
    providers: List[str] = field(default_factory=list)
    models: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    seed: int = 42

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    @classmethod
    def create(
        cls,
        run_id: str,
        benchmark_id: str,
        benchmark_version: str,
        benchmark_fingerprint: str,
        providers: List[str],
        models: List[str],
        parameters: Dict[str, Any] | None = None,
        seed: int = 42,
    ) -> ExecutionManifest:
        """Construct an ExecutionManifest capturing active environment state."""
        try:
            res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
            git_commit = res.stdout.strip()
        except Exception:
            git_commit = "unknown"

        python_ver = sys.version.split()[0]
        plat_info = f"{platform.system()}-{platform.release()}"
        
        config_bytes = json.dumps(parameters or {}, sort_keys=True).encode("utf-8")
        config_hash = hashlib.sha256(config_bytes).hexdigest()

        return cls(
            schema_version="1.0.0",
            run_id=run_id,
            git_commit=git_commit,
            python_version=python_ver,
            platform_info=plat_info,
            config_hash=config_hash,
            benchmark_id=benchmark_id,
            benchmark_version=benchmark_version,
            benchmark_fingerprint=benchmark_fingerprint,
            providers=providers,
            models=models,
            parameters=parameters or {},
            seed=seed,
        )
