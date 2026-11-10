"""Async PostgreSQL pool lifecycle and availability handling."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg
from fastapi import HTTPException


@asynccontextmanager
async def database_pool(dsn: str) -> AsyncIterator[asyncpg.Pool]:
    try:
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=10)
    except (OSError, asyncpg.PostgresError) as exc:
        raise RuntimeError("Database is unavailable") from exc
    try:
        yield pool
    finally:
        await pool.close()


def database_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail="Database unavailable")
