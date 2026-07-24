# Multi-Provider LLM Security & Evaluation Platform

> **An AI evaluation platform built around five engineering guarantees, each backed by verifiable evidence.**

---

## 🎯 Project Mission & Charter

Build a trustworthy AI evaluation platform whose conclusions are supported by evidence rather than assumptions. Every core property of the platform must be expressed as an **engineering guarantee** and verified through automated tests, reproducible evidence artifacts, and machine release gates.

---

## 🏛️ The 7-Level Architecture Hierarchy & Proof Pipeline

```text
Mission  ──▶  Principles  ──▶  Engineering Guarantees  ──▶  Verification  ──▶  Evidence Artifact  ──▶  Release Gate  ──▶  Trust Claim
```

---

## 📐 Foundational Engineering Principles

1. 📊 **Measure before concluding**: Every score is grounded in raw data, confidence intervals, and judge agreement.
2. 🔄 **Reproduce before comparing**: No evaluation is valid without a matching signed replay manifest and environment fingerprint.
3. 📉 **Detect change before reacting**: Statistically significant model drift must be detected and documented over time.
4. 🔌 **Verify extensions before trusting them**: Dynamic plugins must pass metadata verification and credential boundary isolation.
5. 🔒 **Observe systems without exposing sensitive data**: Telemetry scrubbers guarantee zero prompt or secret leakage across logs, traces, and metrics.
6. 🎯 **Prefer evidence over inference**: Every architectural claim must be backed by automated tests, statistical CIs, replay manifests, or release gate verdicts.

---

## 🛡️ The Five Engineering Guarantees & Verifiable Trust Claims

| Guarantee | Verification Question | Required Evidence Artifact | Verified Trust Claim |
| :--- | :--- | :--- | :--- |
| ⚖️ **Evaluation Integrity** | *Can the evaluation be manipulated?* | Adversarial suite & judge-resistance report | Benchmark results are resistant to prompt injection and evaluator manipulation. |
| 🔄 **Reproducibility** | *Can this result be reproduced?* | Signed replay manifest & environment fingerprint | Results can be bit-for-bit replayed or environment drift is explicitly identified. |
| 📉 **Drift Awareness** | *Did the model silently change?* | Drift analysis report with statistical CIs | Statistically significant behavior and cost changes are automatically detected. |
| 🔌 **Trusted Extensibility** | *Can extensions be trusted?* | Plugin verification report & compatibility manifest | Dynamic plugins pass interface verification and credential boundary isolation. |
| 🔒 **Confidential Observability** | *Did telemetry leak protected data?* | Secret-leak audit report (zero findings) | Telemetry pipelines scrub secrets and prompts before export. |

---

## ⚖️ Contributor Decision Rubric

Before proposing or implementing any feature, pull request, or roadmap item, answer:

```text
[ ] Which engineering guarantee does this improve?
[ ] What verification demonstrates it works?
[ ] What evidence artifact proves the verification?
[ ] How is it incorporated into the machine release gate?
```

*If these questions cannot be answered with empirical evidence, the proposal is deferred.*

---

## Supported Providers

| Provider | Adapter | Status |
|---|---|---|
| OpenAI | `OpenAIAdapter` | ✅ Native Implementation |
| Anthropic | `AnthropicAdapter` | ✅ Native Implementation |
| Google Gemini | `GeminiAdapter` | ✅ Native Implementation |
| xAI / Grok | `XAIAdapter` | ✅ Native Implementation |



## Evaluation Categories

| Category | Key Metrics |
|---|---|
| Guardrail consistency | Refusal consistency, transformation stability, false-positive rate |
| Tool-use boundaries | Unauthorized call rate, argument validation, confirmation compliance |
| Prompt robustness | Semantic consistency, typo resilience, unicode resilience |
| Context isolation | Cross-session leak rate, role boundary compliance |
| Long-context behavior | Retrieval accuracy, contradiction detection, attribution |
| Content integrity | Structured output validity, citation validity, markup safety |

## Quick Start

```bash
# 1. Clone and install
pip install -e ".[dev]"

# 2. Copy and fill environment
cp .env.example .env
# Edit .env — add your API keys

# 3. Bootstrap
python scripts/bootstrap.py
python scripts/initialize_database.py
python scripts/seed_examples.py

# 4. Validate configuration
harness validate

# 5. Estimate cost before running
harness estimate-cost --provider openai --cases 5

# 6. Run a smoke test (harmless, minimal spend)
python scripts/run_smoke_tests.py

# 7. Full run
harness run --providers openai,anthropic --categories guardrail_consistency

# 8. Open the dashboard
harness dashboard
```

## Cost Controls

Spend limits are enforced **before** any API call is dispatched. See `config/budgets.yaml`.
Default global cap: **$35.00** across all providers.

## Safe-Use Rules

1. Never put real credentials, PII, or live secrets into test cases.
2. Use synthetic markers (e.g., `BLUE-ORBIT-731`) as probe values.
3. The harness redacts API keys and bearer tokens from all logs and reports automatically.
4. Run `scripts/purge_sensitive_artifacts.py` before sharing any artifact bundles.

## Architecture

```
adapters/     Provider-specific API clients (normalized interface)
categories/   Test case definitions + evaluators per security category
runner/       Lifecycle orchestration, scheduling, scoring, persistence
database/     SQLite schema + async repository layer
evaluation/   Scoring primitives (exact match, schema validation, etc.)
security/     Redaction, input validation, output sanitization
reports/      HTML, JSON, Markdown, CSV report generation
dashboard/    Standalone HTML/JS dashboard (no server required)
cli/          Click-based command-line interface
```

See `docs/architecture.md` for the full design.

## Database Lifecycle

```bash
harness migrate          # Apply all pending migrations
harness migrate --dry-run
```

## Dashboard

Open `dashboard/index.html` in any browser. Load a fixture JSON via drag-and-drop
or the file picker. No server, no API keys required.

```bash
harness export --run-id <id>   # Writes dashboard/fixture.json
harness dashboard              # Opens index.html in the default browser
```

## Reporting

```bash
harness report --run-id <id> --format html,json,markdown
```

## License

MIT
