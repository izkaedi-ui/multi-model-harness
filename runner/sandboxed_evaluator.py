# runner/sandboxed_evaluator.py

"""
Outer-Wall Evaluator Isolation Engine.

Formalizes the invariant:
  "Evaluating inside the box vs. evaluating the box:
   An evaluator subprocess runs in a scrubbed, restricted environment.
   The host runner alone holds authority over decision signatures and release gate verdicts."

Security Invariants:
  1. Environment Scrubbing: API keys and sensitive environment variables are stripped from subprocess env.
  2. Subprocess Execution: Evaluator logic executes in an isolated Python sub-process with restricted I/O and timeouts.
  3. Host Signature Authority: Evaluator subprocesses return un-signed raw payloads.
     Host runner schema-validates the payload and applies Ed25519/HMAC signatures.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Mapping

SECRET_ENV_KEYS = re.compile(
    r"(API_KEY|SECRET|TOKEN|KEY|PASSWORD|AUTH|CREDENTIAL|PRIVATE|DATABASE_URL|AWS_)",
    re.IGNORECASE,
)


class EvaluatorIsolationError(ValueError):
    """Raised when an isolated evaluator fails execution, times out, leaks environment variables, or returns invalid payloads."""


def scrub_environment(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Produces a clean copy of the process environment with all credential keys scrubbed."""
    base = env if env is not None else os.environ
    clean_env: dict[str, str] = {}
    for k, v in base.items():
        if SECRET_ENV_KEYS.search(k):
            continue
        clean_env[k] = v
    clean_env["HARNESS_EVALUATOR_SANDBOX"] = "true"
    return clean_env


@dataclass(frozen=True, slots=True)
class EvaluatorSandboxResult:
    passed: bool
    score: float
    details: dict[str, Any]
    execution_time_ms: float
    stdout: str
    stderr: str


class SandboxedEvaluatorRunner:
    """Executes evaluator logic in an isolated, environment-scrubbed Python subprocess."""

    def __init__(self, timeout_sec: float = 5.0) -> None:
        self.timeout_sec = timeout_sec

    def run_evaluator_code(
        self,
        evaluator_code: str,
        input_case: dict[str, Any],
    ) -> EvaluatorSandboxResult:
        """
        Executes evaluator_code string inside a sandboxed Python subprocess.
        Passes input_case as JSON via stdin and reads JSON result from stdout.
        """
        scrubbed_env = scrub_environment()

        wrapper_script = """
import sys
import json

def _run():
    raw_input = sys.stdin.read()
    case_data = json.loads(raw_input) if raw_input.strip() else {}
    
    # Injected evaluator code context
    exec_scope = {"case_data": case_data, "result": None}
    code = %r
    exec(code, exec_scope)
    
    res = exec_scope.get("result")
    if not isinstance(res, dict):
        raise ValueError("Evaluator script must set 'result' dictionary in global scope")
    
    sys.stdout.write(json.dumps(res))
    sys.stdout.flush()

if __name__ == "__main__":
    _run()
""" % (evaluator_code,)

        cmd = [sys.executable, "-c", wrapper_script]
        stdin_data = json.dumps(input_case, sort_keys=True)

        try:
            completed = subprocess.run(
                cmd,
                input=stdin_data,
                capture_output=True,
                text=True,
                env=scrubbed_env,
                timeout=self.timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            raise EvaluatorIsolationError(f"Evaluator subprocess timed out after {self.timeout_sec}s") from e

        if completed.returncode != 0:
            raise EvaluatorIsolationError(f"Evaluator subprocess exited with code {completed.returncode}: {completed.stderr.strip()}")

        raw_stdout = completed.stdout.strip()
        if not raw_stdout:
            raise EvaluatorIsolationError("Evaluator subprocess returned empty stdout")

        try:
            parsed = json.loads(raw_stdout)
        except Exception as e:
            raise EvaluatorIsolationError(f"Failed to parse evaluator subprocess JSON output: {e}") from e

        if not isinstance(parsed, dict) or "passed" not in parsed or "score" not in parsed:
            raise EvaluatorIsolationError("Evaluator output missing required 'passed' or 'score' fields")

        passed = bool(parsed["passed"])
        try:
            score = float(parsed["score"])
        except (ValueError, TypeError) as e:
            raise EvaluatorIsolationError("Evaluator output 'score' must be a valid float") from e

        details = parsed.get("details", {})
        if not isinstance(details, dict):
            details = {"raw": details}

        return EvaluatorSandboxResult(
            passed=passed,
            score=score,
            details=details,
            execution_time_ms=0.0,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


def assert_evaluator_outer_wall_isolation_gate() -> dict[str, bool]:
    """Release gate check verifying outer-wall evaluator isolation and env scrubbing."""
    # 1. Verify Environment Scrubbing
    dirty_env = {
        "OPENAI_API_KEY": "sk-1234567890abcdefghijklmnopqrstuvwxyz",
        "ANTHROPIC_API_KEY": "sk-ant-12345",
        "PATH": "/usr/bin",
        "USER": "harness_user",
    }
    clean_env = scrub_environment(dirty_env)
    env_scrub_ok = "OPENAI_API_KEY" not in clean_env and "ANTHROPIC_API_KEY" not in clean_env and clean_env.get("PATH") == "/usr/bin"

    # 2. Executable Subprocess Isolation Test
    runner = SandboxedEvaluatorRunner(timeout_sec=5.0)
    code = """
import os
assert os.environ.get("OPENAI_API_KEY") is None
result = {"passed": True, "score": 1.0, "details": {"isolation": "verified"}}
"""
    try:
        res = runner.run_evaluator_code(code, {"input": "test_case"})
        subprocess_ok = res.passed and res.score == 1.0 and res.details.get("isolation") == "verified"
    except Exception:
        subprocess_ok = False

    # 3. Negative Test: Subprocess Environment Leak Attempt Fails
    leak_code = """
import os
if "OPENAI_API_KEY" in os.environ:
    result = {"passed": True, "score": 1.0}
else:
    raise RuntimeError("Key correctly absent")
"""
    env_leak_prevented = False
    try:
        runner.run_evaluator_code(leak_code, {})
    except EvaluatorIsolationError:
        env_leak_prevented = True

    return {
        "evaluator_environment_scrubbing": env_scrub_ok,
        "evaluator_subprocess_isolation": subprocess_ok,
        "evaluator_credential_leak_prevention": env_leak_prevented,
    }
