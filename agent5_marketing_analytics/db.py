"""Postgres connection pool + schema bootstrap for Agent 5."""

from __future__ import annotations

import logging
from pathlib import Path

import asyncpg

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

_pool: asyncpg.Pool | None = None


async def get_pool(database_url: str) -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=database_url, min_size=1, max_size=5)
    return _pool


async def apply_schema(database_url: str) -> None:
    """Create tables if they don't exist yet. Safe to call on every startup."""
    pool = await get_pool(database_url)
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    async with pool.acquire() as conn:
        await conn.execute(sql)
    logger.info("Schema applied (tables created if missing)")
