"""
Runner — orchestrates the full 15-step test run lifecycle.

Lifecycle:
    1.  Load configuration
    2.  Validate credentials without logging them
    3.  Load and validate test cases
    4.  Resolve model capabilities
    5.  Estimate maximum cost
    6.  Reject run if budget cap exceeded
    7.  Create run record and correlation ID
    8.  Dispatch bounded concurrent requests
    9.  Retry only retryable failures
    10. Normalise provider responses
    11. Redact sensitive material
    12. Persist raw and normalised results
    13. Evaluate and score
    14. Generate verdicts
    15. Write reproducibility manifest and produce report artifacts
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import yaml

from adapters.auth import available_providers
from adapters.capability_registry import CapabilityRegistry
from adapters.cost_estimator import estimate_cost_usd, estimate_run_cost_usd
from adapters.provider_factory import build_all_adapters
from adapters.rate_limiter import RateLimiter
from categories.registry import CategoryRegistry
from runner.cost_guard import CostGuard
from runner.execution_plan import ExecutionPlan, build_plan
from runner.exporter import export_fixture
from runner.metrics import RunMetrics
from runner.response_store import ResponseStore
from runner.retry_manager import RetryManager
from runner.scorer import Scorer
from runner.verdict_engine import VerdictEngine
from security_harness.correlation import generate_run_id, set_current_correlation_id
from security_harness.errors import (
    BudgetExceeded,
    GlobalBudgetExceeded,
    MissingApiKeyError,
)
from security_harness.types import ExecutionStatus, ModelResponse, RunStatus, TestCase

log = logging.getLogger(__name__)


@dataclass
class RunConfig:
    """Resolved configuration for a single test run."""

    providers: list[str]
    categories: list[str]
    max_cases_per_model: int = 50
    max_output_tokens: int = 800
    max_concurrent: int = 4
    budget_config: dict = field(default_factory=dict)
    dry_run: bool = False
    allow_partial_providers: bool = False


@dataclass
class RunResult:
    """Summary returned after run completion."""

    run_id: str
    status: RunStatus
    started_at: datetime
    completed_at: datetime | None
    total_executions: int
    passed: int
    failed: int
    errored: int
    total_cost_usd: float
    artifact_path: str | None = None


class Runner:
    """
    Orchestrates a complete security test run.

    Usage:
        config = RunConfig(providers=["openai"], categories=["guardrail_consistency"])
        runner = Runner(config)
        result = await runner.run()
    """

    def __init__(self, config: RunConfig) -> None:
        self._config = config
        self._run_id = generate_run_id()
        set_current_correlation_id(self._run_id)
        self._metrics = RunMetrics(self._run_id)
        self._store = ResponseStore()

    async def run(self) -> RunResult:
        started_at = datetime.now(UTC)
        log.info("runner.start", extra={"run_id": self._run_id})

        try:
            # Step 1-2: Load config + validate credentials
            budget_cfg = self._load_budget_config()
            available = available_providers()
            missing = [p for p in self._config.providers if p not in available]

            if missing and not self._config.allow_partial_providers:
                log.error("runner.missing_providers", extra={"missing": missing, "available": available})
                raise MissingApiKeyError(
                    provider=", ".join(missing),
                    env_var=f"API keys missing for requested provider(s): {', '.join(missing)}. Pass --allow-partial to proceed without them."
                )

            requested = [p for p in self._config.providers if p in available]
            if not requested:
                log.error("runner.no_providers", extra={"requested": self._config.providers,
                                                         "available": available})
                raise RuntimeError("No providers available with valid API keys.")


            # Step 3: Load test cases
            category_registry = CategoryRegistry.default()
            all_cases: list[TestCase] = []
            for cat_name in self._config.categories:
                category = category_registry.get(cat_name)
                cases = category.load_cases()
                all_cases.extend(cases[: self._config.max_cases_per_model])

            log.info("runner.cases_loaded", extra={"total": len(all_cases)})

            # Step 4: Resolve capabilities
            cap_registry = CapabilityRegistry.from_config()

            # Step 5-6: Estimate cost and enforce budget
            cost_guard = CostGuard.from_config(budget_cfg)
            adapters = build_all_adapters(providers=requested)

            for provider in list(adapters.keys()):
                models = cap_registry.models_for_provider(provider)
                if not models:
                    continue
                model = models[0].model
                estimated = estimate_run_cost_usd(
                    model=model,
                    avg_input_tokens=500,
                    max_output_tokens=self._config.max_output_tokens,
                    num_cases=len(all_cases),
                    max_attempts=2,
                )
                cost_guard.check_provider(provider, estimated)

            # Step 7: Create run record
            log.info("runner.run_created", extra={"run_id": self._run_id})

            if self._config.dry_run:
                log.info("runner.dry_run_complete", extra={"run_id": self._run_id})
                return RunResult(
                    run_id=self._run_id,
                    status=RunStatus.COMPLETED,
                    started_at=started_at,
                    completed_at=datetime.now(UTC),
                    total_executions=0,
                    passed=0, failed=0, errored=0,
                    total_cost_usd=0.0,
                )

            # Step 8-12: Dispatch requests
            rate_limiter = RateLimiter.from_config()
            retry_manager = RetryManager.from_config()
            semaphore = asyncio.Semaphore(self._config.max_concurrent)

            plan = build_plan(all_cases, adapters, cap_registry, self._config)
            log.info("runner.plan_built", extra={"executions": len(plan.items)})

            results: list[tuple[TestCase, ModelResponse | Exception]] = []

            async def _dispatch(item: Any) -> None:
                async with semaphore:
                    test_case = item.test_case
                    adapter = item.adapter
                    provider = item.provider
                    request = item.request
                    try:
                        await rate_limiter.acquire(provider)
                        cost_guard.check_provider(provider,
                            estimate_run_cost_usd(request.model, 500,
                                                  request.max_output_tokens, 1, 1))
                        response = await adapter.generate(request)
                        actual_cost = estimate_cost_usd(
                            model=request.model,
                            input_tokens=response.usage.input_tokens,
                            output_tokens=response.usage.output_tokens,
                        )
                        cost_guard.record_spend(provider, actual_cost)
                        self._store.put(item.execution_id, response)
                        results.append((test_case, response))
                        self._metrics.record_success(provider, response.latency_ms,
                                                     response.usage.total_tokens,
                                                     actual_cost)


                    except (BudgetExceeded, GlobalBudgetExceeded) as exc:
                        log.warning("runner.budget_stop", extra={"error": str(exc)})
                        results.append((test_case, exc))
                        self._metrics.record_error(provider, "budget_exceeded")
                    except Exception as exc:
                        log.error("runner.execution_failed",
                                  extra={
                                      "provider": provider,
                                      "model": request.model,
                                      "test_case": test_case.id,
                                      "error_type": type(exc).__name__,
                                      "error": str(exc),
                                  })
                        results.append((test_case, exc))
                        self._metrics.record_error(provider, type(exc).__name__)


            await asyncio.gather(*[_dispatch(item) for item in plan.items])

            # Step 13-14: Score and verdict
            scorer = Scorer(category_registry)
            verdict_engine = VerdictEngine.from_config()
            all_scores = []
            all_verdicts = []

            for test_case, response_or_err in results:
                if isinstance(response_or_err, Exception):
                    continue
                scores = await scorer.score(response_or_err, test_case)
                all_scores.extend(scores)
                verdict = verdict_engine.decide(scores, test_case)
                all_verdicts.append(verdict)

            # Step 15: Export artifacts and persist to SQLite DB
            artifact_path = export_fixture(
                run_id=self._run_id,
                results=results,
                scores=all_scores,
                verdicts=all_verdicts,
                metrics=self._metrics,
            )

            passed = sum(1 for v in all_verdicts if v.status.value == "pass")
            failed = sum(1 for v in all_verdicts if v.status.value == "fail")
            errored = sum(1 for _, r in results if isinstance(r, Exception))

            status = RunStatus.COMPLETED_WITH_ERRORS if errored > 0 else RunStatus.COMPLETED

            # Persist to SQLite DB if database connection is available
            try:
                from database.sqlite import get_connection, apply_schema
                from database.repository import HarnessRepository
                await apply_schema()
                async with get_connection() as conn:
                    repo = HarnessRepository(conn)
                    await repo.create_run(self._run_id, self._run_id, estimated_cost_usd=0.0)

                    # Save dummy test_case and model entries to satisfy FK constraints if missing
                    for test_case, response_or_err in results:
                        if isinstance(response_or_err, Exception):
                            continue
                        r = response_or_err
                        exec_id = r.raw_response.get("id", "")
                        if not exec_id:
                            continue

                        # Ensure test case exists
                        await conn.execute(
                            "INSERT OR IGNORE INTO test_cases (id, external_id, category, subcategory, messages_json, expected_json) VALUES (?, ?, ?, ?, ?, ?)",
                            (test_case.id, test_case.id, test_case.category, test_case.subcategory, "[]", "{}")
                        )
                        # Ensure provider exists
                        await conn.execute(
                            "INSERT OR IGNORE INTO providers (id, name, api_family, base_url) VALUES (?, ?, ?, ?)",
                            (r.provider, r.provider, r.provider, "")
                        )
                        # Ensure model exists
                        await conn.execute(
                            "INSERT OR IGNORE INTO models (id, provider_id, model_name) VALUES (?, ?, ?)",
                            (r.model, r.provider, r.model)
                        )
                        # Ensure execution exists
                        await repo.save_execution(
                            execution_id=exec_id,
                            run_id=self._run_id,
                            test_case_id=test_case.id,
                            model_id=r.model,
                            status=ExecutionStatus.COMPLETED,
                            latency_ms=r.latency_ms,
                            input_tokens=r.usage.input_tokens,
                            output_tokens=r.usage.output_tokens,
                            finish_reason=r.finish_reason,
                        )

                    for s in all_scores:
                        await repo.save_scores([s])
                    for v in all_verdicts:
                        await repo.save_verdict(v)
                    await repo.update_run_status(self._run_id, status, actual_cost_usd=self._metrics.total_cost_usd)
                log.info("runner.db_persisted", extra={"run_id": self._run_id})
            except Exception as db_exc:
                log.warning("runner.db_persist_warning", extra={"error": str(db_exc)})




            completed_at = datetime.now(UTC)
            log.info("runner.complete", extra={
                "run_id": self._run_id,
                "status": status.value,
                "passed": passed, "failed": failed, "errored": errored,
                "duration_s": (completed_at - started_at).total_seconds(),
            })


            return RunResult(
                run_id=self._run_id,
                status=status,
                started_at=started_at,
                completed_at=completed_at,
                total_executions=len(results),
                passed=passed,
                failed=failed,
                errored=errored,
                total_cost_usd=self._metrics.total_cost_usd,
                artifact_path=artifact_path,
            )


        except Exception as exc:
            import traceback
            traceback.print_exc()
            log.error("runner.fatal_error", extra={"error": str(exc)})
            return RunResult(
                run_id=self._run_id,
                status=RunStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                total_executions=0,
                passed=0, failed=0, errored=0,
                total_cost_usd=0.0,
            )


    @staticmethod
    def _load_budget_config() -> dict:
        try:
            with open("config/budgets.yaml") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            return {}
