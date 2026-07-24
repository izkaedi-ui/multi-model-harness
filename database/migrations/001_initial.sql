-- Migration 001: Initial schema (see schema.sql for full DDL)
-- This file is intentionally minimal — the full schema is in schema.sql.
-- Migrations 002+ handle additive changes only.

-- Mark this migration applied
CREATE TABLE IF NOT EXISTS _migrations (
    id          TEXT PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
INSERT OR IGNORE INTO _migrations (id) VALUES ('001_initial');
