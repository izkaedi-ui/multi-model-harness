# Multi-Provider LLM Security & Evaluation Platform

> A reproducible security evaluation framework for benchmarking, validating, and comparing Large Language Models across multiple providers.

[![Release](https://img.shields.io/github/v/release/izkaedi-ui/multi-model-harness)](../../releases)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Evaluate OpenAI, Anthropic, Gemini, xAI, and other providers using reproducible security benchmarks, automated scoring, signed evidence artifacts, statistical analysis, and machine-verifiable release gates.

---

# Features

- Multi-provider LLM evaluation
- Security-focused benchmark suite
- Reproducible execution manifests
- Statistical scoring & confidence metrics
- Cost estimation before execution
- Provider plugin architecture
- Standalone HTML dashboard
- Machine-verifiable release gate
- Signed decision provenance (SHA-256 + Ed25519)
- Secret-safe telemetry & logging
- SQLite-backed execution history
- Fully configurable benchmark DSL

---

# Supported Providers

| Provider | Adapter | Status |
|-----------|---------|--------|
| OpenAI | `OpenAIAdapter` | ✅ |
| Anthropic | `AnthropicAdapter` | ✅ |
| Google Gemini | `GeminiAdapter` | ✅ |
| xAI / Grok | `XAIAdapter` | ✅ |

---

# Evaluation Categories

| Category | Example Metrics |
|-----------|----------------|
| Guardrail Consistency | Refusal consistency, transformation stability |
| Tool Use Boundaries | Unauthorized tool calls, argument validation |
| Prompt Robustness | Typo resilience, Unicode resilience |
| Context Isolation | Cross-session leakage detection |
| Long Context Behavior | Retrieval accuracy, contradiction detection |
| Content Integrity | Structured output validity, citation accuracy |

---

# Quick Start

## 1. Install

```bash
git clone https://github.com/izkaedi-ui/multi-model-harness.git
cd multi-model-harness

pip install -e ".[dev]"
```

## 2. Configure

```bash
cp .env.example .env
```

Edit `.env` and add your provider API keys.

---

## 3. Bootstrap

```bash
python scripts/bootstrap.py
python scripts/initialize_database.py
python scripts/seed_examples.py
```

---

## 4. Validate

```bash
harness validate
```

---

## 5. Estimate Cost

```bash
harness estimate-cost \
    --provider openai \
    --cases 5
```

---

## 6. Smoke Test

```bash
python scripts/run_smoke_tests.py
```

---

## 7. Run Benchmarks

```bash
harness run \
    --providers openai,anthropic \
    --categories guardrail_consistency
```

---

## 8. Launch Dashboard

```bash
harness dashboard
```

---

# Engineering Guarantees

The platform is built around seven engineering guarantees. Every guarantee is validated through automated verification and produces evidence artifacts.

| Engineering Guarantee | Verification | Evidence Artifact |
|-----------------------|--------------|-------------------|
| Evaluation Integrity | Judge-resistance tests | `reports/judge_resistance.json` |
| Reproducibility | Replay validation | Signed execution manifests |
| Drift Awareness | Historical comparisons | SQLite execution database |
| Trusted Extensibility | Plugin validation | Plugin manifests |
| Confidential Observability | Telemetry verification | Telemetry audit logs |
| Object Authorization | Authorization tests | Object authorization reports |
| Decision Provenance | Cryptographic verification | Signed decision records |

---

# Release Gate

Every release must successfully pass the automated release gate.

Current checks include:

- ✅ Compilation
- ✅ Unit Tests
- ✅ Configuration Validation
- ✅ Benchmark DSL Validation
- ✅ Database Integrity
- ✅ Evaluation Integrity
- ✅ Object Authorization
- ✅ Decision Provenance
- ✅ Telemetry Safety
- ✅ Environment Isolation

A release is considered production-ready only after all release checks pass.

Example:

```text
===========================================
 Multi-Provider Harness Release Readiness
===========================================

Compilation................PASS
Unit Tests.................PASS
Validation.................PASS
Database Integrity.........PASS
Evaluation Integrity.......PASS
Decision Provenance........PASS

VERDICT: READY FOR RELEASE
```

---

# Project Architecture

```
adapters/
benchmark_dsl/
categories/
cli/
dashboard/
database/
evaluation/
reports/
runner/
security/
telemetry/
tests/
```

Additional architecture documentation is available under:

```
docs/
```

---

# Cost Controls

API spending is enforced **before** any provider requests are dispatched.

Default global budget:

```
$35.00
```

Configuration:

```
config/budgets.yaml
```

---

# Dashboard

Export results:

```bash
harness export --run-id <RUN_ID>
```

Launch:

```bash
harness dashboard
```

The dashboard is completely static and requires no backend server.

---

# Reporting

Generate reports in multiple formats.

```bash
harness report \
    --run-id <RUN_ID> \
    --format html,json,markdown
```

---

# Database Lifecycle

Apply migrations:

```bash
harness migrate
```

Preview migrations:

```bash
harness migrate --dry-run
```

---

# Safe Usage

- Never use production credentials.
- Never include real customer data.
- Use synthetic markers (for example `BLUE-ORBIT-731`) when testing context isolation.
- API keys and bearer tokens are automatically redacted.
- Run:

```bash
python scripts/purge_sensitive_artifacts.py
```

before sharing artifacts publicly.

---

# Project Mission

Build an AI evaluation platform whose conclusions are supported by reproducible evidence rather than assumptions.

Every architectural claim should be backed by:

- Automated testing
- Statistical evidence
- Replay manifests
- Cryptographic verification
- Machine-verifiable release gates

---

# Contributor Checklist

Before implementing any feature, answer:

- [ ] Which engineering guarantee does this improve?
- [ ] Which automated verification proves it?
- [ ] What evidence artifact demonstrates it?
- [ ] How is it incorporated into the release gate?

Features that cannot answer these questions with empirical evidence should not be merged.

---

# Roadmap

- [ ] Additional provider adapters
- [ ] Distributed benchmark execution
- [ ] Automatic drift alerts
- [ ] Interactive benchmark authoring
- [ ] Web dashboard improvements
- [ ] Additional benchmark categories
- [ ] CI/CD release automation

---

# License

MIT License

---

## Repository Status

| Component | Status |
|-----------|--------|
| Release Gate | ✅ Passing |
| Unit Tests | ✅ Passing |
| Decision Provenance | ✅ Verified |
| Evaluation Integrity | ✅ Verified |
| Object Authorization | ✅ Verified |
| GitHub Releases | ✅ Published |
| Tagged Release | **v0.6.3** |

---

Built for trustworthy, reproducible, evidence-based evaluation of modern Large Language Models.
