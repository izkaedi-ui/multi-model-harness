-- Security Test Harness — SQLite schema
-- Apply via: harness migrate

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- -----------------------------------------------------------------------
-- test_cases
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS test_cases (
    id              TEXT PRIMARY KEY,
    external_id     TEXT NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    category        TEXT NOT NULL,
    subcategory     TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    messages_json   TEXT NOT NULL,       -- JSON array
    expected_json   TEXT NOT NULL,       -- JSON object
    tags_json       TEXT NOT NULL DEFAULT '[]',
    content_hash    TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- -----------------------------------------------------------------------
-- providers
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS providers (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL UNIQUE,
    api_family          TEXT NOT NULL,
    base_url            TEXT NOT NULL,
    configuration_hash  TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- -----------------------------------------------------------------------
-- models
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS models (
    id                      TEXT PRIMARY KEY,
    provider_id             TEXT NOT NULL REFERENCES providers(id),
    model_name              TEXT NOT NULL,
    context_limit           INTEGER NOT NULL DEFAULT 4096,
    max_output_tokens       INTEGER NOT NULL DEFAULT 800,
    supports_tools          INTEGER NOT NULL DEFAULT 0,
    supports_system_messages INTEGER NOT NULL DEFAULT 1,
    supports_json_schema    INTEGER NOT NULL DEFAULT 0,
    pricing_metadata_json   TEXT NOT NULL DEFAULT '{}',
    first_seen_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    last_seen_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(provider_id, model_name)
);

-- -----------------------------------------------------------------------
-- runs
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS runs (
    id                  TEXT PRIMARY KEY,
    correlation_id      TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending',
    started_at          TEXT,
    completed_at        TEXT,
    configuration_hash  TEXT NOT NULL DEFAULT '',
    git_commit          TEXT NOT NULL DEFAULT '',
    environment_json    TEXT NOT NULL DEFAULT '{}',
    budget_limit_usd    REAL NOT NULL DEFAULT 35.0,
    estimated_cost_usd  REAL NOT NULL DEFAULT 0.0,
    actual_cost_usd     REAL NOT NULL DEFAULT 0.0,
    failure_reason      TEXT
);

-- -----------------------------------------------------------------------
-- executions
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS executions (
    id                  TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL REFERENCES runs(id),
    test_case_id        TEXT NOT NULL REFERENCES test_cases(id),
    model_id            TEXT NOT NULL REFERENCES models(id),
    attempt_number      INTEGER NOT NULL DEFAULT 1,
    request_timestamp   TEXT,
    response_timestamp  TEXT,
    latency_ms          INTEGER,
    status              TEXT NOT NULL DEFAULT 'pending',
    finish_reason       TEXT,
    input_tokens        INTEGER NOT NULL DEFAULT 0,
    output_tokens       INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd  REAL NOT NULL DEFAULT 0.0,
    request_hash        TEXT NOT NULL DEFAULT '',
    response_hash       TEXT NOT NULL DEFAULT ''
);

-- -----------------------------------------------------------------------
-- responses
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS responses (
    id                      TEXT PRIMARY KEY,
    execution_id            TEXT NOT NULL REFERENCES executions(id),
    raw_response_json       TEXT,       -- redacted before storage
    normalized_text         TEXT,
    tool_calls_json         TEXT NOT NULL DEFAULT '[]',
    provider_metadata_json  TEXT NOT NULL DEFAULT '{}',
    redaction_applied       INTEGER NOT NULL DEFAULT 0,
    artifact_path           TEXT
);

-- -----------------------------------------------------------------------
-- scores
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scores (
    id                  TEXT PRIMARY KEY,
    execution_id        TEXT NOT NULL REFERENCES executions(id),
    evaluator_name      TEXT NOT NULL,
    evaluator_version   TEXT NOT NULL,
    metric_name         TEXT NOT NULL,
    numeric_score       REAL NOT NULL,
    pass_threshold      REAL NOT NULL,
    passed              INTEGER NOT NULL,
    confidence          REAL NOT NULL,
    explanation         TEXT NOT NULL DEFAULT ''
);

-- -----------------------------------------------------------------------
-- verdicts
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS verdicts (
    id                      TEXT PRIMARY KEY,
    execution_id            TEXT NOT NULL REFERENCES executions(id),
    status                  TEXT NOT NULL,   -- pass | warn | fail | needs_review | inconclusive
    severity                TEXT NOT NULL,   -- low | medium | high | critical
    confidence              REAL NOT NULL,
    requires_human_review   INTEGER NOT NULL DEFAULT 0,
    review_notes            TEXT NOT NULL DEFAULT '',
    blocking_metric         TEXT,
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- -----------------------------------------------------------------------
-- Indexes
-- -----------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_executions_run_id ON executions(run_id);
CREATE INDEX IF NOT EXISTS idx_executions_test_case ON executions(test_case_id);
CREATE INDEX IF NOT EXISTS idx_scores_execution ON scores(execution_id);
CREATE INDEX IF NOT EXISTS idx_verdicts_execution ON verdicts(execution_id);
CREATE INDEX IF NOT EXISTS idx_verdicts_status ON verdicts(status);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
