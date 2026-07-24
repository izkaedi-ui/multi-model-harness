# Omega Supreme Bootstrap — Execution Topology Inventory

## Repository Identification
- **Path**: `F:\multi-model-harness`
- **Branch**: `main`
- **Baseline Commit**: `399b73a7d0494f09a627da4f6dc31e09ae4d2462`
- **Latest Tag**: `v0.2.8`
- **Python Version**: `3.14.3`

## Component Inventory
1. **Adapters (`adapters/`)**:
   - `base_adapter.py`: Abstract `BaseAdapter` interface with retry, cost tracking, logging.
   - `openai_adapter.py`: Native `OpenAIAdapter` and `XAIAdapter` sub-class.
   - `anthropic_adapter.py`: Native `AnthropicAdapter` implementation.
   - `gemini_adapter.py`: Native `GeminiAdapter` implementation.
   - `cost_estimator.py`: Longest-prefix model pricing lookup table.
   - `provider_factory.py`: Static provider construction dictionary.

2. **Runner & Storage (`runner/`, `database/`)**:
   - `runner.py`: Async execution pipeline, budget enforcement, DB persistence.
   - `repository.py`: SQLite `HarnessRepository` schema & CRUD ops (`harness.db`).
   - `transactions.py`: Async transaction manager with automatic rollback on error.

3. **CLI Operational Layer (`cli/main.py`)**:
   - `doctor`: Validates keys, SQLite schema, model registry.
   - `discover-models`: Discovers active provider endpoint models.
   - `leaderboard`: Renders cross-provider execution metrics & costs.
   - `optimize`: Performs SQLite WAL checkpoint & VACUUM optimization.
   - `backfill-costs`: Backfills historical executions with longest-prefix costs.
   - `release-check`: Comprehensive release gate with pure JSON output streaming.

4. **Security & Redaction (`security/`)**:
   - `secret_redactor.py`: Redacts API keys, bearer tokens, and sensitive dictionary fields.
   - `artifact_scanner.py`: Scans generated HTML/JSON fixtures for secret leakage.
   - `input_validator.py`: Validates JSONL test case schemas.

5. **Test Suite (`tests/`)**:
   - 34 passing unit tests covering provider identity, error mapping, cost reconciliation, CLI output purity, and secret scrubbing.
