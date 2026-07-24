-- Migration 003: Add error details and model tracking to executions table
ALTER TABLE executions ADD COLUMN error_type TEXT;
ALTER TABLE executions ADD COLUMN error_message TEXT;
ALTER TABLE executions ADD COLUMN configured_model TEXT;
ALTER TABLE executions ADD COLUMN returned_model TEXT;

INSERT OR IGNORE INTO _migrations (id) VALUES ('003_cost_tracking');
