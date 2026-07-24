"""
Async context manager for database transactions.

Usage:
    async with async_transaction(conn) as tx:
        await tx.execute("INSERT INTO runs ...")
        await tx.execute("INSERT INTO executions ...")
    # Commits on exit, rolls back on exception
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aiosqlite


@asynccontextmanager
async def async_transaction(
    conn: aiosqlite.Connection,
) -> AsyncGenerator[aiosqlite.Connection, None]:
    """
    Run a block of database operations as an atomic transaction.

    Commits on success, rolls back on any exception.
    """
    try:
        yield conn
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
