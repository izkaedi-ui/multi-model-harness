"""
Async SQLite connection helper.

Provides a context manager for aiosqlite connections with WAL mode,
foreign keys enabled, and row factory set to aiosqlite.Row.
"""

from __future__ import annotations

import pathlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import aiosqlite

_DEFAULT_DB_PATH = "harness.db"


@asynccontextmanager
async def get_connection(
    db_path: str = _DEFAULT_DB_PATH,
) -> AsyncGenerator[aiosqlite.Connection, None]:
    """
    Async context manager that yields an aiosqlite connection.

    Enables WAL mode and foreign keys. Sets row_factory to aiosqlite.Row
    so rows can be accessed by column name.
    """
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode = WAL")
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute("PRAGMA synchronous = NORMAL")
        yield conn


async def apply_schema(db_path: str = _DEFAULT_DB_PATH) -> None:
    """
    Apply the base schema.sql to a fresh database.

    Idempotent — uses CREATE TABLE IF NOT EXISTS throughout.
    """
    schema_path = pathlib.Path("database/schema.sql")
    sql = schema_path.read_text(encoding="utf-8")

    async with get_connection(db_path) as conn:
        await conn.executescript(sql)
        await conn.commit()


async def apply_migrations(db_path: str = _DEFAULT_DB_PATH) -> list[str]:
    """
    Apply all pending migrations from database/migrations/*.sql in order.

    Returns a list of migration IDs that were applied.
    """
    migrations_dir = pathlib.Path("database/migrations")
    migration_files = sorted(migrations_dir.glob("*.sql"))

    applied: list[str] = []

    async with get_connection(db_path) as conn:
        # Ensure tracking table exists
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS _migrations "
            "(id TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')))"
        )
        await conn.commit()

        for migration_file in migration_files:
            migration_id = migration_file.stem
            row = await conn.execute(
                "SELECT id FROM _migrations WHERE id = ?", (migration_id,)
            )
            if await row.fetchone():
                continue  # Already applied

            sql = migration_file.read_text(encoding="utf-8")
            await conn.executescript(sql)
            await conn.commit()
            applied.append(migration_id)

    return applied
