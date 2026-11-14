"""Fixtures for the data model tests.

The model is applied with the real db/sql/apply.sh to a throwaway database
(TEST_DATABASE, observatory_test by default) on the compose postgres server,
so the observatory database itself is never touched.

Run inside the compose network:

    docker compose -f compose.yaml -f compose.dev.yaml run --rm tests pytest tests/db -v
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

REPO_ROOT = Path(__file__).resolve().parents[2]
APPLY_SCRIPT = REPO_ROOT / "db" / "sql" / "apply.sh"
TEST_DATABASE = os.environ.get("TEST_DATABASE", "observatory_test")

# Reference data loaded by the model itself; never emptied between tests.
PRESERVED_TABLES = {("core", "dim_country"), ("core", "dim_date")}

ROLE_CREDENTIALS = {
    "owner": ("PGUSER", "PGPASSWORD"),
    "writer": ("observatory_writer", "DB_WRITER_PASSWORD"),
    "reader": ("observatory_reader", "DB_READER_PASSWORD"),
}


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required to run the database tests")
    return value


def conninfo(role: str, dbname: str) -> str:
    """Build a libpq connection string for one of the three model roles."""
    if role not in ROLE_CREDENTIALS:
        raise ValueError(f"Unknown role {role!r}; expected one of {sorted(ROLE_CREDENTIALS)}")
    user_source, password_variable = ROLE_CREDENTIALS[role]
    user = _required_env(user_source) if role == "owner" else user_source
    return make_conninfo(
        host=_required_env("PGHOST"),
        port=os.environ.get("PGPORT", "5432"),
        user=user,
        password=_required_env(password_variable),
        dbname=dbname,
    )


@pytest.fixture(scope="session")
def test_database() -> Iterator[str]:
    """Create TEST_DATABASE from scratch and apply the full model to it."""
    if TEST_DATABASE == os.environ.get("POSTGRES_DB"):
        raise RuntimeError("TEST_DATABASE must differ from POSTGRES_DB: the tests drop it")

    identifier = sql.Identifier(TEST_DATABASE)
    with psycopg.connect(conninfo("owner", "postgres"), autocommit=True) as admin:
        admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(identifier))
        admin.execute(sql.SQL("CREATE DATABASE {}").format(identifier))

    result = subprocess.run(
        [str(APPLY_SCRIPT), TEST_DATABASE],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            f"apply.sh failed with code {result.returncode}\n"
            f"--- stdout\n{result.stdout}\n--- stderr\n{result.stderr}",
            pytrace=False,
        )

    yield TEST_DATABASE

    with psycopg.connect(conninfo("owner", "postgres"), autocommit=True) as admin:
        admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(identifier))


@pytest.fixture(autouse=True)
def clean_tables(test_database: str) -> None:
    """Empty every core and replay table except the reference dimensions."""
    with psycopg.connect(conninfo("owner", test_database), autocommit=True) as conn:
        rows = conn.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema IN ('core', 'replay') AND table_type = 'BASE TABLE'
            ORDER BY table_schema, table_name
            """
        ).fetchall()
        tables = [sql.Identifier(schema, name) for schema, name in rows if (schema, name) not in PRESERVED_TABLES]
        if tables:
            conn.execute(sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(sql.SQL(", ").join(tables)))


@pytest.fixture
def connect(test_database: str) -> Iterator[Callable[..., psycopg.Connection]]:
    """Open connections as owner, writer or reader with a chosen search_path.

    connect("writer", search_path="replay, core") targets the replay schema the
    same way the consumer does for the earthquakes.replay topic.
    """
    opened: list[psycopg.Connection] = []

    def _connect(role: str = "owner", search_path: str = "core", autocommit: bool = True) -> psycopg.Connection:
        path = ",".join(part.strip() for part in search_path.split(","))
        conn = psycopg.connect(
            conninfo(role, test_database),
            autocommit=autocommit,
            options=f"-c search_path={path}",
        )
        opened.append(conn)
        return conn

    yield _connect
    for conn in opened:
        conn.close()


@pytest.fixture
def owner_conn(connect: Callable[..., psycopg.Connection]) -> psycopg.Connection:
    return connect("owner")


@pytest.fixture
def writer_conn(connect: Callable[..., psycopg.Connection]) -> psycopg.Connection:
    return connect("writer")


@pytest.fixture
def reader_conn(connect: Callable[..., psycopg.Connection]) -> psycopg.Connection:
    return connect("reader")
