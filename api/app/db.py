"""PostgreSQL pools of the API: observatory_reader, read only, one per mode.

The mode of a request picks the pool, never the text of a query: the live pool has
search_path «core» and the replay pool «replay, core» (dim_country always comes from
core). A request uses exactly one pool, so a response can never mix both schemas.

The API must answer GET /api/salud even when the database is down, so the pools are
opened in the background and retried with backoff; until a pool exists, requests that
need it get 503 and the health endpoint says «degraded». A failure of the replay pool
does not affect the live one.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal

import asyncpg
from fastapi import FastAPI, Request

from common.db import create_pool
from common.settings import DatabaseSettings

logger = logging.getLogger(__name__)

Mode = Literal["live", "replay"]
MODES: tuple[Mode, ...] = ("live", "replay")

SEARCH_PATHS: dict[str, str] = {"live": "core", "replay": "replay, core"}
POOL_SIZES: dict[str, int] = {"live": 10, "replay": 5}
COMMAND_TIMEOUT_SECONDS = 10.0

# Failures that mean «the database cannot answer», never «there are no events».
DATABASE_ERRORS: tuple[type[BaseException], ...] = (
    OSError,
    TimeoutError,
    asyncio.TimeoutError,
    asyncpg.PostgresError,
    asyncpg.InterfaceError,
)


class DatabaseUnavailable(Exception):
    """The pool of the requested mode does not exist yet or the database failed."""


async def connect_in_background(app: FastAPI, mode: str, settings: DatabaseSettings) -> None:
    """Set app.state.pools[mode] once PostgreSQL accepts the reader role."""
    app.state.pools[mode] = await create_pool(
        settings,
        SEARCH_PATHS[mode],
        application_name=f"api-{mode}",
        max_size=POOL_SIZES[mode],
        command_timeout=COMMAND_TIMEOUT_SECONDS,
    )
    logger.info("Database pool %s ready as %s", mode, settings.user)


def start(app: FastAPI, settings: DatabaseSettings) -> list[asyncio.Task]:
    app.state.pools = {mode: None for mode in MODES}
    return [asyncio.create_task(connect_in_background(app, mode, settings)) for mode in MODES]


async def stop(app: FastAPI, tasks: list[asyncio.Task]) -> None:
    for task in tasks:
        task.cancel()
    for task in tasks:
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001 - shutting down
            pass
    for pool in app.state.pools.values():
        if pool is not None:
            await pool.close()


def pool_for(request: Request, mode: str) -> asyncpg.Pool:
    pool = request.app.state.pools.get(mode)
    if pool is None:
        raise DatabaseUnavailable(f"The {mode} database pool is not available")
    return pool


@contextmanager
def guard() -> Iterator[None]:
    """Turn any database failure into DatabaseUnavailable: never «no events» as a valid answer."""
    try:
        yield
    except DatabaseUnavailable:
        raise
    except DATABASE_ERRORS as exc:
        logger.error("Database query failed: %s: %s", type(exc).__name__, exc)
        raise DatabaseUnavailable("The database could not answer the query") from exc
