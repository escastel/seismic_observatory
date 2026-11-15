"""asyncpg access to the test database, as the services connect (observatory_writer)."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from typing import TypeVar

import asyncpg

from common.db import open_pool
from common.settings import DatabaseSettings

T = TypeVar("T")


def writer_settings(test_database: str) -> DatabaseSettings:
    return DatabaseSettings(
        host=os.environ["PGHOST"],
        port=int(os.environ.get("PGPORT", "5432")),
        database=test_database,
        user="observatory_writer",
        password=os.environ["DB_WRITER_PASSWORD"],
    )


async def writer_pool(test_database: str, search_path: str = "core") -> asyncpg.Pool:
    return await open_pool(writer_settings(test_database), search_path, application_name="tests", max_size=4)


def run_with_pool(test_database: str, body: Callable[[asyncpg.Pool], Awaitable[T]], search_path: str = "core") -> T:
    """Run body(pool) in a fresh event loop and close the pool afterwards."""

    async def main() -> T:
        pool = await writer_pool(test_database, search_path)
        try:
            return await body(pool)
        finally:
            await pool.close()

    return asyncio.run(main())


def run_with_conn(test_database: str, body: Callable[[asyncpg.Connection], Awaitable[T]], search_path: str = "core") -> T:
    async def with_conn(pool: asyncpg.Pool) -> T:
        async with pool.acquire() as conn:
            return await body(conn)

    return run_with_pool(test_database, with_conn, search_path)
