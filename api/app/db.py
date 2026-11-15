"""PostgreSQL pool of the API: observatory_reader, read only.

The API must answer GET /api/salud even when the database is down, so the
pool is opened in the background and retried with backoff; until it exists,
requests that need data get 503 and the health endpoint says «degraded».
"""

from __future__ import annotations

import asyncio
import logging

import asyncpg
from fastapi import FastAPI, HTTPException

from common.db import create_pool
from common.settings import DatabaseSettings

logger = logging.getLogger(__name__)

LIVE_SEARCH_PATH = "core"


async def connect_in_background(app: FastAPI, settings: DatabaseSettings) -> None:
    """Set app.state.db_pool once PostgreSQL accepts the reader role."""
    app.state.db_pool = await create_pool(settings, LIVE_SEARCH_PATH, application_name="api", max_size=10)
    logger.info("Database pool ready as %s", settings.user)


def start(app: FastAPI, settings: DatabaseSettings) -> asyncio.Task:
    app.state.db_pool = None
    return asyncio.create_task(connect_in_background(app, settings))


async def stop(app: FastAPI, task: asyncio.Task) -> None:
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):  # noqa: BLE001 - shutting down
        pass
    pool: asyncpg.Pool | None = app.state.db_pool
    if pool is not None:
        await pool.close()


def database_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail="Database unavailable")
