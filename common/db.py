"""asyncpg pools bound to one search_path (contracts/database.md, «Conexión»)."""

from __future__ import annotations

import logging

import asyncpg

from .retry import retry
from .settings import DatabaseSettings

logger = logging.getLogger(__name__)

# Connection failures worth waiting for: server not up yet, network, restarts.
TRANSIENT_ERRORS: tuple[type[BaseException], ...] = (
    OSError,
    asyncpg.CannotConnectNowError,
    asyncpg.TooManyConnectionsError,
    asyncpg.ConnectionDoesNotExistError,
    asyncpg.InvalidCatalogNameError,
    asyncpg.InvalidAuthorizationSpecificationError,
)


async def open_pool(
    settings: DatabaseSettings,
    search_path: str,
    *,
    application_name: str,
    min_size: int = 1,
    max_size: int = 5,
    command_timeout: float | None = None,
) -> asyncpg.Pool:
    """Create a pool once; every connection gets the given search_path.

    Statements stay unqualified: changing target (core or replay) is changing
    the search_path, never the text of a query.
    """
    return await asyncpg.create_pool(
        settings.dsn(),
        min_size=min_size,
        max_size=max_size,
        command_timeout=command_timeout,
        server_settings={"search_path": search_path, "application_name": application_name},
    )


async def create_pool(
    settings: DatabaseSettings,
    search_path: str,
    *,
    application_name: str,
    min_size: int = 1,
    max_size: int = 5,
    command_timeout: float | None = None,
) -> asyncpg.Pool:
    """open_pool, retried with exponential backoff until PostgreSQL answers."""
    return await retry(
        lambda: open_pool(
            settings,
            search_path,
            application_name=application_name,
            min_size=min_size,
            max_size=max_size,
            command_timeout=command_timeout,
        ),
        description=f"connecting to PostgreSQL {settings.host}:{settings.port} as {settings.user} ({search_path})",
        retry_on=TRANSIENT_ERRORS,
        log=logger,
    )
