-- Migration 002: Add aggregate scores view
CREATE VIEW IF NOT EXISTS v_run_scores AS
SELECT
    e.run_id,
    e.id AS execution_id,
    s.metric_name,
    s.numeric_score,
    s.passed,
    s.confidence,
    v.status AS verdict_status
FROM executions e
JOIN scores s ON s.execution_id = e.id
LEFT JOIN verdicts v ON v.execution_id = e.id;

INSERT OR IGNORE INTO _migrations (id) VALUES ('002_scores');
