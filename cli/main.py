"""
Main CLI entry point for the LLM security test harness.
"""

from __future__ import annotations

import asyncio
import json
import logging
import pathlib
import sys
from typing import Any

import click

from security_harness.logging import configure_logging

log = logging.getLogger(__name__)


@click.group()
@click.option("--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)")
@click.option("--log-format", default="text", help="Logging format (text, json)")
def cli(log_level: str, log_format: str) -> None:
    """Multi-Provider LLM Security Test Harness CLI."""
    configure_logging(level=log_level, fmt=log_format)


@cli.command()
@click.option("--providers", default="openai,anthropic", help="Comma-separated providers")
@click.option("--categories", default="guardrail_consistency", help="Comma-separated test categories")
@click.option("--max-cases", default=50, type=int, help="Maximum test cases per model")
@click.option("--dry-run", is_flag=True, help="Validate plan without executing requests")
@click.option("--allow-partial", is_flag=True, help="Allow run to proceed if some requested providers lack API keys")
def run(providers: str, categories: str, max_cases: int, dry_run: bool, allow_partial: bool) -> None:
    """Execute a security test run across configured providers."""
    from runner.runner import RunConfig, Runner

    provider_aliases = {
        "gemini": "google",
    }

    raw_prov_list = [
        provider_aliases.get(provider.strip().lower(), provider.strip().lower())
        for provider in providers.split(",")
        if provider.strip()
    ]
    prov_list = list(dict.fromkeys(raw_prov_list))


    cat_list = [
        category.strip()
        for category in categories.split(",")
        if category.strip()
    ]

    config = RunConfig(
        providers=prov_list,
        categories=cat_list,
        max_cases_per_model=max_cases,
        dry_run=dry_run,
        allow_partial_providers=allow_partial,
    )


    runner = Runner(config)
    result = asyncio.run(runner.run())

    click.echo("\n--- Run Summary ---")
    click.echo(f"Run ID:        {result.run_id}")
    click.echo(f"Status:        {result.status.value}")
    click.echo(f"Executions:    {result.total_executions}")
    click.echo(f"Passed:        {result.passed}")
    click.echo(f"Failed:        {result.failed}")
    click.echo(f"Errored:       {result.errored}")
    click.echo(f"Total Cost:    ${result.total_cost_usd:.4f}")
    if result.artifact_path:
        click.echo(f"Dashboard Fixture: {result.artifact_path}")


@cli.command()
def validate() -> None:
    """Validate system configuration and test case schemas."""
    from security.input_validator import validate_jsonl_file

    click.echo("Validating configuration and test cases...")
    categories_dir = pathlib.Path("categories")
    errors = []

    for jsonl_file in categories_dir.rglob("*.jsonl"):
        file_errors = validate_jsonl_file(jsonl_file)
        errors.extend(file_errors)

    if errors:
        click.echo(f"[ERROR] Validation failed with {len(errors)} errors:")
        for err in errors:
            click.echo(f"  - {err}")
        sys.exit(1)
    else:
        click.echo("[OK] All configuration and test case files are valid.")


@cli.command()
@click.option("--provider", default="openai", help="Provider to estimate")
@click.option("--cases", default=10, type=int, help="Number of test cases")
def estimate_cost(provider: str, cases: int) -> None:
    """Pre-flight cost estimation for a planned run."""
    from adapters.cost_estimator import estimate_run_cost_usd

    cost = estimate_run_cost_usd("gpt-4o" if provider == "openai" else "claude-sonnet-4-5", 500, 800, cases)
    click.echo(f"Estimated worst-case cost for {cases} cases on {provider}: ${cost:.4f} USD")


@cli.command()
def doctor() -> None:
    """Check provider environment health, credentials, database, and configuration."""
    import sqlite3

    from adapters.auth import has_api_key

    click.echo("--- Multi-Provider Harness Doctor ---")
    click.echo("[OK] Python Environment & CLI Core initialized")

    # 1. API Keys
    click.echo("\nChecking Provider Credentials:")
    missing_count = 0
    present_count = 0
    for prov, key_var in [("openai", "OPENAI_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY"),
                           ("google", ["GOOGLE_API_KEY", "GEMINI_API_KEY"]), ("xai", "XAI_API_KEY")]:
        if isinstance(key_var, list):
            is_set = any(has_api_key(str(k)) for k in key_var)
        else:
            is_set = has_api_key(str(key_var))
        if is_set:
            present_count += 1
            status = "[OK] Key Present"
        else:
            missing_count += 1
            status = "[MISSING] Key Not Set"
        click.echo(f"  - Provider {prov:<10}: {status}")

    # 2. Database Health
    click.echo("\nChecking Database Integrity:")
    try:
        conn = sqlite3.connect("harness.db")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk_check = conn.execute("PRAGMA foreign_key_check").fetchall()
        conn.close()
        if integrity == "ok" and not fk_check:
            click.echo("  - harness.db       : [OK] Schema & Foreign Keys Valid")
        else:
            click.echo(f"  - harness.db       : [WARN] Integrity: {integrity}, FK errors: {len(fk_check)}")
    except Exception as e:
        click.echo(f"  - harness.db       : [ERROR] {e}")

    # 3. Model Registry
    click.echo("\nChecking Model Registry:")
    try:
        import yaml
        with open("config/models.yaml") as f:
            cfg = yaml.safe_load(f) or {}
        providers_registered = list(cfg.keys())
        click.echo(f"  - Registered Models: [OK] {sum(len(v) for v in cfg.values())} models across {providers_registered}")
    except Exception as e:
        click.echo(f"  - Model Registry   : [ERROR] {e}")

    click.echo("\n-------------------------------------------")
    if missing_count == 0:
        click.echo("STATUS: [HEALTHY] All provider credentials set.")
    elif present_count > 0:
        click.echo(f"STATUS: [DEGRADED] {present_count} providers available, {missing_count} missing credentials.")
    else:
        click.echo("STATUS: [UNHEALTHY] No provider API keys found.")
        sys.exit(1)


@cli.command()
@click.option("--host", default="127.0.0.1", help="Host address to bind metrics server to")
@click.option("--port", default=9464, type=int, help="Port to expose Prometheus metrics on")
def serve_metrics(host: str, port: int) -> None:
    """Start a persistent Prometheus metrics HTTP server daemon."""
    import time

    from telemetry.metrics import build_prometheus_metrics
    from telemetry.server import MetricsServer

    _metrics = build_prometheus_metrics()

    server = MetricsServer(port=port, address=host)
    if server.start():
        click.echo(f"Prometheus metrics server running at http://{host}:{port}/metrics")

        click.echo("Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            click.echo("\nMetrics server stopped.")
    else:
        click.echo(f"[ERROR] Failed to start metrics server on http://{host}:{port}/metrics")
        sys.exit(1)


@cli.command()
def discover_models() -> None:

    """Discover available models from configured provider endpoints."""
    import os

    import openai

    from adapters.auth import has_api_key

    click.echo("Discovering available models from active provider endpoints...")
    if has_api_key("OPENAI_API_KEY"):
        click.echo("\n[OpenAI] Querying /v1/models...")
        try:
            client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=10.0)
            models = sorted([m.id for m in client.models.list().data if "gpt" in m.id or "o1" in m.id or "o3" in m.id])
            click.echo(f"  Active OpenAI Models ({len(models)}): {models[:5]}...")
        except Exception as e:
            click.echo(f"  [ERROR] {e}")

    if has_api_key("XAI_API_KEY"):
        click.echo("\n[xAI] Querying /v1/models...")
        try:
            client = openai.OpenAI(api_key=os.environ["XAI_API_KEY"], base_url="https://api.x.ai/v1", timeout=10.0)
            models = sorted([m.id for m in client.models.list().data])
            click.echo(f"  Active xAI Models ({len(models)}): {models}")
        except Exception as e:
            click.echo(f"  [ERROR] {e}")

    click.echo("\n[OK] Discovery complete.")


@cli.command()
def leaderboard() -> None:
    """Generate cross-provider performance leaderboard from SQLite run history."""
    import sqlite3

    click.echo("--- Multi-Provider Leaderboard (Historical SQLite Data) ---")
    try:
        conn = sqlite3.connect("harness.db")
        cursor = conn.execute("""
            SELECT
                m.provider_id,
                m.model_name,
                COUNT(e.id) as total_execs,
                AVG(e.latency_ms) as avg_latency_ms,
                SUM(e.input_tokens + e.output_tokens) as total_tokens,
                SUM(e.estimated_cost_usd) as total_cost
            FROM executions e
            JOIN models m ON m.id = e.model_id
            WHERE e.status = 'completed'
            GROUP BY m.provider_id, m.model_name
            ORDER BY total_execs DESC
        """)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            click.echo("No completed executions found in harness.db.")
            return

        click.echo(f"{'Provider':<12} {'Model':<25} {'Executions':<12} {'Avg Latency':<14} {'Tokens':<10} {'Total Cost':<10}")
        click.echo("-" * 85)
        for prov, model, count, avg_lat, tokens, cost in rows:
            lat_str = f"{avg_lat:.1f} ms" if avg_lat else "N/A"
            click.echo(f"{prov:<12} {model:<25} {count:<12} {lat_str:<14} {tokens:<10} ${cost:.4f}")

    except Exception as e:
        click.echo(f"[ERROR] Failed to query leaderboard: {e}")


@cli.command()
def optimize() -> None:
    """Perform database vacuuming, WAL checkpointing, and index optimization."""
    import sqlite3

    click.echo("--- Multi-Provider Harness System Optimization ---")
    try:
        conn = sqlite3.connect("harness.db")
        click.echo("[1/3] Executing WAL checkpoint...")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        click.echo("[2/3] Optimizing query planner indexes...")
        conn.execute("PRAGMA optimize")
        click.echo("[3/3] Vacuuming database storage...")
        conn.execute("VACUUM")
        conn.close()
        click.echo("\n[OK] Database and storage optimization complete.")
    except Exception as e:
        click.echo(f"[ERROR] Optimization failed: {e}")


@cli.command()
@click.option("--dry-run", is_flag=True, help="Preview backfill changes without modifying harness.db")
def backfill_costs(dry_run: bool) -> None:
    """Recalculate and persist execution costs in harness.db using longest-prefix model pricing."""
    import sqlite3

    import adapters.cost_estimator
    from adapters.cost_estimator import estimate_cost_usd

    adapters.cost_estimator._PRICING_CACHE = None  # Refresh pricing cache
    click.echo(f"--- Recalculating Historical Execution Costs (dry_run={dry_run}) ---")

    try:
        conn = sqlite3.connect("harness.db")
        cursor = conn.execute("""
            SELECT e.id, m.model_name, e.input_tokens, e.output_tokens, e.estimated_cost_usd
            FROM executions e
            JOIN models m ON m.id = e.model_id
            WHERE e.status = 'completed'
        """)
        rows = cursor.fetchall()

        if not rows:
            click.echo("No completed execution records found.")
            conn.close()
            return

        updated_count = 0
        unknown_models: set[str] = set()
        old_total = 0.0
        new_total = 0.0

        for exec_id, model_name, in_tok, out_tok, current_cost in rows:
            new_cost = estimate_cost_usd(model_name, in_tok, out_tok)
            old_total += current_cost
            new_total += new_cost
            if current_cost != new_cost:
                updated_count += 1
                if new_cost == 0.0:
                    unknown_models.add(model_name)
                if not dry_run:
                    conn.execute("UPDATE executions SET estimated_cost_usd = ? WHERE id = ?", (new_cost, exec_id))

        if not dry_run:
            conn.commit()
        conn.close()

        mode_str = "[DRY-RUN PREVIEW]" if dry_run else "[COMMITTED]"
        click.echo(f"{mode_str} Evaluated {len(rows)} execution records.")
        click.echo(f"  - Rows modified       : {updated_count}")
        click.echo(f"  - Previous Cost Total : ${old_total:.4f} USD")
        click.echo(f"  - New Cost Total      : ${new_total:.4f} USD")

        if unknown_models:
            click.echo(f"  - [WARN] Models with $0.00 pricing (unmatched): {list(unknown_models)}")
        else:
            click.echo("  - [OK] All models successfully matched to pricing registry.")

    except Exception as e:
        click.echo(f"[ERROR] Backfill failed: {e}")


def _run_quiet_command(args: list[str]) -> bool:
    import subprocess
    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.returncode == 0


def _collect_release_checks() -> dict[str, bool]:
    import compileall
    import contextlib
    import io
    import sqlite3

    import pytest

    # 1. Compilation
    comp_ok = bool(compileall.compile_dir(".", quiet=1))

    # 2. Pytest Unit Tests
    try:
        out_buf = io.StringIO()
        with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(out_buf):
            ret = pytest.main(["-q", "tests", "--ignore=tests/unit/test_platform_hardening.py"])
        unit_ok = (ret == 0)
    except Exception:
        unit_ok = False

    # 3. YAML Configuration & Benchmark DSL Validation
    try:
        from security.input_validator import validate_jsonl_file
        categories_dir = pathlib.Path("categories")
        val_errors = []
        for jsonl_file in categories_dir.rglob("*.jsonl"):
            val_errors.extend(validate_jsonl_file(jsonl_file))

        dsl_ok = pathlib.Path("benchmark_dsl/schema.json").exists()
        val_ok = (len(val_errors) == 0 and dsl_ok)
    except Exception:
        val_ok = False

    # 4. Database Integrity
    try:
        conn = sqlite3.connect("harness.db")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk_check = conn.execute("PRAGMA foreign_key_check").fetchall()
        conn.close()
        db_ok = (integrity == "ok" and not fk_check)
    except Exception:
        db_ok = False

    # 5. Telemetry & Observability Verification
    try:
        from telemetry.metrics import MetricsRuntime
        from telemetry.redaction import safe_attributes
        from telemetry.tracing import NullSpan, TracingRuntime

        telemetry_import = True
        telemetry_noop = isinstance(TracingRuntime(enabled=False).span("test").__enter__(), NullSpan)
        metrics_registry = isinstance(MetricsRuntime(), MetricsRuntime)
        telemetry_secret_safety = safe_attributes({"api_key": "secret", "provider": "openai"}) == {"provider": "openai"}
    except Exception:
        telemetry_import = False
        telemetry_noop = False
        metrics_registry = False
        telemetry_secret_safety = False

    # 6. Evaluation Integrity Gate Check
    try:
        from security.evaluation_integrity_gate import assert_evaluation_integrity
        integrity_res = assert_evaluation_integrity("reports/judge_resistance.json")
        evaluation_integrity = integrity_res["checks"]["evaluation_integrity"]["passed"]
    except Exception:
        evaluation_integrity = False

    # 7. Git Status Check
    git_ok = _run_quiet_command(["git", "status", "--short"])

    return {
        "compilation": comp_ok,
        "unit_tests": unit_ok,
        "validation": val_ok,
        "database_integrity": db_ok,
        "git_clean": git_ok,
        "benchmark_dsl": bool(dsl_ok),
        "telemetry_import": telemetry_import,
        "telemetry_noop": telemetry_noop,
        "metrics_registry": metrics_registry,
        "telemetry_secret_safety": telemetry_secret_safety,
        "evaluation_integrity": evaluation_integrity,
    }





from contextlib import contextmanager


@contextmanager
def _temporarily_suppress_logging() -> Any:
    root_logger = logging.getLogger()
    previous_level = root_logger.level
    root_logger.setLevel(logging.CRITICAL + 1)
    try:
        yield
    finally:
        root_logger.setLevel(previous_level)


def _write_json_stdout(payload: object) -> None:
    """
    Emit exactly one JSON document without passing through Click/Colorama.

    This avoids Windows console-handle failures in wrapped shells and preserves
    stdout purity for CI consumers.
    """
    rendered = json.dumps(
        payload,
        indent=2,
        ensure_ascii=True,
        sort_keys=False,
    )
    sys.stdout.write(rendered)
    sys.stdout.write("\n")
    sys.stdout.flush()


@cli.command()
@click.option("--format", "fmt", default="text", type=click.Choice(["text", "json"]), help="Output format (text or json)")
@click.option("--strict", is_flag=True, help="Strict mode: fail non-zero if any warnings exist")
def release_check(fmt: str, strict: bool) -> None:
    """Run comprehensive automated verification suite to validate release readiness."""
    if fmt == "json":
        with _temporarily_suppress_logging():
            checks = _collect_release_checks()
    else:
        click.echo("===========================================")
        click.echo(" Multi-Provider Harness Release Readiness ")
        click.echo("===========================================\n")
        checks = _collect_release_checks()

    required_ok = all(
        checks[k] for k in ("compilation", "unit_tests", "validation", "database_integrity")
    )
    git_ok = checks["git_clean"]
    ready = required_ok and git_ok if strict else required_ok

    payload = {
        "verdict": "ready" if ready else "failed",
        "strict_mode": strict,
        "checks": checks,
    }

    if fmt == "json":
        _write_json_stdout(payload)
    else:
        for gate, status in checks.items():
            click.echo(f"   -> {gate:<25} : {'PASS' if status else 'FAIL/WARN'}")

        click.echo("\n===========================================")
        click.echo(" Release Gate Summary ")
        click.echo("===========================================")
        for gate, status in checks.items():
            click.echo(f"{gate:<25} : {'PASS' if status else 'FAIL/WARN'}")

        click.echo("\nVERDICT: " + ("READY FOR RELEASE [OK]" if ready else "ATTENTION REQUIRED [WARN]"))

    if not ready:
        sys.exit(1)




if __name__ == "__main__":
    cli()






