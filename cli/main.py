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
def dashboard() -> None:
    """Open the standalone HTML dashboard in the default browser."""
    import webbrowser
    path = pathlib.Path("dashboard/index.html").resolve()
    click.echo(f"Opening dashboard at {path.as_uri()}")
    webbrowser.open(path.as_uri())


if __name__ == "__main__":
    cli()
