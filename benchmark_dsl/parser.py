"""
Parser and validator for Versioned Benchmark DSL scenarios.
"""
from __future__ import annotations

import os
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Union

from benchmark_dsl.models import Scenario, Step, Assertion
from benchmark_dsl.versioning import calculate_fingerprint
from security_harness.errors import ConfigurationError

MAX_SCENARIO_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


class DSLParser:
    """Parser and validator for YAML and legacy JSONL scenario files."""

    @staticmethod
    def parse_dict(data: Dict[str, Any]) -> Scenario:
        """Parse dictionary payload into a validated Scenario object."""
        if not isinstance(data, dict):
            raise ConfigurationError("Scenario payload must be a dictionary")

        required_keys = ["id", "version", "title", "category", "steps"]
        for k in required_keys:
            if k not in data:
                raise ConfigurationError(f"Missing required Scenario field: {k!r}")

        version = str(data["version"])
        if version not in ("1.0.0", "1.0"):
            raise ConfigurationError(f"Unsupported Benchmark DSL version: {version!r}")

        steps: list[Step] = []
        for raw_step in data["steps"]:
            if not isinstance(raw_step, dict) or "role" not in raw_step or "content" not in raw_step:
                raise ConfigurationError("Step must contain 'role' and 'content'")

            assertions: list[Assertion] = []
            for raw_ast in raw_step.get("assertions", []):
                if not isinstance(raw_ast, dict) or "type" not in raw_ast:
                    raise ConfigurationError("Assertion must contain 'type'")
                assertions.append(Assertion(
                    type=raw_ast["type"],
                    target=raw_ast.get("target", "output"),
                    value=raw_ast.get("value"),
                ))

            steps.append(Step(
                role=raw_step["role"],
                content=raw_step["content"],
                assertions=assertions,
            ))

        fingerprint = calculate_fingerprint(data)
        return Scenario(
            id=str(data["id"]),
            version=version,
            title=str(data["title"]),
            category=str(data["category"]),
            steps=steps,
            metadata=dict(data.get("metadata", {})),
            fingerprint=fingerprint,
        )

    @classmethod
    def parse_file(cls, file_path: Union[str, Path]) -> Scenario:
        """Parse scenario from a YAML or JSON file on disk safely."""
        path = Path(file_path).resolve()
        
        # Security: Prevent path traversal outside allowed directories
        if ".." in str(file_path):
            raise ConfigurationError(f"Path traversal detected in file path: {file_path}")

        if not path.exists():
            raise ConfigurationError(f"Scenario file not found: {file_path}")

        if path.stat().st_size > MAX_SCENARIO_SIZE_BYTES:
            raise ConfigurationError(f"Scenario file exceeds 10MB limit: {file_path}")

        raw_text = path.read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(raw_text)
        elif path.suffix == ".json":
            data = json.loads(raw_text)
        else:
            raise ConfigurationError(f"Unsupported file format: {path.suffix}")

        return cls.parse_dict(data)

    @classmethod
    def parse_legacy_jsonl(cls, jsonl_line: str) -> Scenario:
        """Adapter for legacy single-line JSONL benchmark records."""
        data = json.loads(jsonl_line)
        scenario_data = {
            "id": data.get("id", "legacy_case"),
            "version": "1.0.0",
            "title": data.get("name", data.get("id", "Legacy Benchmark")),
            "category": data.get("category", "general"),
            "steps": [
                {
                    "role": "user",
                    "content": data.get("prompt", ""),
                    "assertions": [
                        {"type": "contains", "value": data.get("expected")}
                    ] if "expected" in data else []
                }
            ],
            "metadata": {k: v for k, v in data.items() if k not in ("id", "name", "category", "prompt", "expected")}
        }
        return cls.parse_dict(scenario_data)
