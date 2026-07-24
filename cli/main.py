"""
Main CLI entry point for the LLM security test harness.
"""

from __future__ import annotations

import asyncio
import json
import logging
import pathlib
import sys

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
    from adapters.auth import available_providers, has_api_key
    from database.sqlite import get_connection, apply_schema
    import sqlite3

    click.echo("--- Multi-Provider Harness Doctor ---")
    click.echo("[OK] Python Environment & CLI Core initialized")

    # 1. API Keys
    click.echo("\nChecking Provider Credentials:")
    for prov, key_var in [("openai", "OPENAI_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY"),
                           ("google", ["GOOGLE_API_KEY", "GEMINI_API_KEY"]), ("xai", "XAI_API_KEY")]:
        status = "[OK] Key Present" if has_api_key(key_var) else "[MISSING] Key Not Set"
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

    click.echo("\n[OK] Health Check Complete.")


@cli.command()
def discover_models() -> None:
    """Discover available models from configured provider endpoints."""
    from adapters.auth import has_api_key
    import os
    import openai

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


if __name__ == "__main__":
    cli()



