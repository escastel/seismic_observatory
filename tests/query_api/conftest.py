"""Fixtures for the API tests (spec 006).

The real application (api.app.main.app) is called through a tiny ASGI client, without
lifespan, against the test database (TEST_DATABASE, observatory_test) shared with
tests/db: never run both suites at once. The tests are synchronous; the harness owns ONE
dedicated asyncio event loop, where the asyncpg pools (role observatory_reader) live.

Fixture `api` (function scope) yields an ApiHarness, with a clean database, open pools
and max_features back to DEFAULT_MAX_FEATURES:

    api.get(path, **params) -> Response       GET; a param value may be a list (repeated key)
    api.request(method, path, headers=None, params=None, body=b"") -> Response
    Response: .status, .headers (lowercase dict), .body (bytes), .json(), .text

    api.app                                    the FastAPI app (api.app.main.app)
    api.set_max_features(n)                    app.state.max_features = n
    api.close_pools()                          close both pools; queries then fail
    api.set_pools_none()                       pools = None, as «not open yet»
    api.reopen_pools()                         open both pools again

    api.add_event(version, schema="core", message=None, replayed_at=None) -> outcome
        version is tests.db.helpers.Version; schema is "core" or "replay"; goes through
        apply_event_version (replay rows get replayed_at, default now)
    api.add_extraction(**overrides) -> extraction_id   (a core.extraction row, outcome ok)
    api.add_quarantine(reason_codes, schema="core", offset=0, **kwargs)
        kwargs as tests.db.helpers.quarantine (event_id, payload, raw_text, is_synthetic)
    api.sql(statement, params=(), schema="core", role="owner") -> list of rows
    api.wipe()                                 empty core and replay except dim_country, dim_date
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb

# Defaults needed to import api.app.main; real values from the environment win.
os.environ.setdefault("POSTGRES_DB", "observatory_test")
os.environ.setdefault("DB_READER_PASSWORD", "unused")
os.environ.setdefault("CORS_ORIGINS", "https://observatorio.netlify.app,http://localhost:4200")

from common.db import open_pool  # noqa: E402
from common.settings import DatabaseSettings  # noqa: E402
from tests.db.conftest import PRESERVED_TABLES, conninfo, test_database  # noqa: E402,F401
from tests.db.helpers import Message, Version, apply_version, quarantine  # noqa: E402
from tests.support.asgi_client import Response, call_asgi  # noqa: E402

DEFAULT_MAX_FEATURES = 1000
SEARCH_PATHS = {"live": "core", "replay": "replay, core"}


class ApiHarness:
    def __init__(self, app: Any, database: str) -> None:
        self.app = app
        self.database = database
        self.loop = asyncio.new_event_loop()
        self.pools: dict[str, Any] = {}
        self._offsets = 0

    # --- lifecycle -----------------------------------------------------------------
    def _run(self, coroutine: Any) -> Any:
        return self.loop.run_until_complete(coroutine)

    def _reader_settings(self) -> DatabaseSettings:
        return DatabaseSettings(
            host=os.environ["PGHOST"],
            port=int(os.environ.get("PGPORT", "5432")),
            database=self.database,
            user="observatory_reader",
            password=os.environ["DB_READER_PASSWORD"],
        )

    def reopen_pools(self) -> None:
        self.close_pools()

        async def open_all() -> dict[str, Any]:
            return {
                mode: await open_pool(
                    self._reader_settings(), path, application_name=f"tests-api-{mode}", max_size=4
                )
                for mode, path in SEARCH_PATHS.items()
            }

        self.pools = self._run(open_all())
        self.app.state.pools = dict(self.pools)

    def close_pools(self) -> None:
        """Close both pools but leave them in app.state: every query then fails."""

        async def close_all() -> None:
            for pool in self.pools.values():
                await pool.close()

        self._run(close_all())

    def set_pools_none(self) -> None:
        self.app.state.pools = {mode: None for mode in SEARCH_PATHS}

    def set_max_features(self, value: int) -> None:
        self.app.state.max_features = value

    def shutdown(self) -> None:
        self.close_pools()
        self.loop.close()

    # --- requests ------------------------------------------------------------------
    def request(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        body: bytes = b"",
    ) -> Response:
        return self._run(call_asgi(self.app, method, path, params, headers, body))

    def get(self, path: str, **params: Any) -> Response:
        return self.request("GET", path, params=params)

    # --- database ------------------------------------------------------------------
    def _connect(self, role: str = "owner", schema: str = "core") -> psycopg.Connection:
        path = "replay,core" if schema == "replay" else "core"
        return psycopg.connect(conninfo(role, self.database), autocommit=True, options=f"-c search_path={path}")

    def sql(self, statement: str, params: tuple = (), schema: str = "core", role: str = "owner") -> list[tuple]:
        with self._connect(role, schema) as conn:
            cursor = conn.execute(statement, params)
            return cursor.fetchall() if cursor.description else []

    def _next_message(self, topic: str) -> Message:
        self._offsets += 1
        return Message(topic, 0, self._offsets)

    def add_event(
        self,
        version: Version,
        schema: str = "core",
        message: Message | None = None,
        replayed_at: datetime | None = None,
    ) -> str:
        topic = "earthquakes.live" if schema == "core" else "earthquakes.replay"
        replayed = replayed_at or (datetime.now(timezone.utc) if schema == "replay" else None)
        with self._connect("writer", schema) as conn:
            return apply_version(conn, version, message or self._next_message(topic), replayed)

    def add_extraction(self, **overrides: Any) -> int:
        values: dict[str, Any] = {
            "source": "usgs_feed",
            "purpose": "live",
            "request_url": "https://earthquake.usgs.gov/test.geojson",
            "requested_at": datetime.now(timezone.utc),
            "outcome": "ok",
            "http_status": 200,
            "attempt_count": 1,
        }
        values.update(overrides)
        columns = sql.SQL(", ").join(sql.Identifier(name) for name in values)
        placeholders = sql.SQL(", ").join(
            sql.Placeholder() for _ in values
        )
        statement = sql.SQL("INSERT INTO core.extraction ({}) VALUES ({}) RETURNING extraction_id").format(
            columns, placeholders
        )
        args = [Jsonb(v) if isinstance(v, (dict, list)) else v for v in values.values()]
        with self._connect("owner") as conn:
            row = conn.execute(statement, args).fetchone()
        assert row is not None
        return row[0]

    def add_quarantine(
        self, reason_codes: list[str], schema: str = "core", offset: int | None = None, **kwargs: Any
    ) -> None:
        topic = "earthquakes.live" if schema == "core" else "earthquakes.replay"
        message = self._next_message(topic) if offset is None else Message(topic, 0, offset)
        if kwargs.get("payload") is None:
            kwargs.setdefault("raw_text", "damaged message")
        with self._connect("writer", schema) as conn:
            quarantine(conn, message, reason_codes, **kwargs)

    def wipe(self) -> None:
        """Empty core and replay except the reference dimensions (as tests/db clean_tables)."""
        with self._connect("owner") as conn:
            rows = conn.execute(
                """
                SELECT table_schema, table_name FROM information_schema.tables
                WHERE table_schema IN ('core', 'replay') AND table_type = 'BASE TABLE'
                ORDER BY table_schema, table_name
                """
            ).fetchall()
            tables = [sql.Identifier(s, n) for s, n in rows if (s, n) not in PRESERVED_TABLES]
            if tables:
                conn.execute(sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(sql.SQL(", ").join(tables)))
        self._offsets = 0


@pytest.fixture(scope="session")
def _api_harness(test_database: str) -> Iterator[ApiHarness]:
    from api.app.main import app  # lazy: main.py may be mid-rewrite when collecting

    harness = ApiHarness(app, test_database)
    harness.reopen_pools()
    yield harness
    harness.shutdown()


@pytest.fixture
def api(_api_harness: ApiHarness) -> ApiHarness:
    _api_harness.wipe()
    _api_harness.reopen_pools()
    _api_harness.set_max_features(DEFAULT_MAX_FEATURES)
    return _api_harness
