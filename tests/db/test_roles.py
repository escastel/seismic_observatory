"""Least privilege of the application roles (FR-011)."""

from __future__ import annotations

import psycopg
import pytest

from tests.db.helpers import Version, apply_version, utc


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO publish_state (event_id, updated_at) VALUES ('E9', now())",
        "UPDATE event_current SET magnitude = 9",
        "DELETE FROM event_current",
        "INSERT INTO dim_country VALUES ('ZZZ', 'Z', 'Z', 'Z', 'Z', NULL)",
    ],
)
@pytest.mark.parametrize("schema", ["core", "replay, core"])
def test_reader_cannot_change_rows(connect, statement: str, schema: str) -> None:
    reader = connect("reader", search_path=schema)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        reader.execute(statement)


def test_reader_cannot_apply_versions(reader_conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        apply_version(reader_conn, Version("E1", utc("2026-11-14 10:05")))


@pytest.mark.parametrize(
    "statement",
    [
        "CREATE TABLE core.intruder (id int)",
        "CREATE TABLE replay.intruder (id int)",
        "CREATE TABLE public.intruder (id int)",
        "DROP TABLE core.event_current",
        "DROP TABLE replay.event_version",
        "ALTER TABLE core.event_current ADD COLUMN extra int",
        "TRUNCATE core.event_current",
    ],
)
def test_writer_cannot_run_ddl(writer_conn: psycopg.Connection, statement: str) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        writer_conn.execute(statement)


def test_writer_cannot_change_the_dimensions(writer_conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        writer_conn.execute("UPDATE dim_country SET name_es = 'X' WHERE country_id = 'ESP'")


def test_writer_writes_rows_in_both_schemas(connect) -> None:
    core = connect("writer", search_path="core")
    replay = connect("writer", search_path="replay, core")
    assert apply_version(core, Version("E1", utc("2026-11-14 10:05"))) == "new"
    assert apply_version(replay, Version("E1", utc("2026-11-14 10:05")), replayed_at=utc("2026-11-14 12:00")) == "new"
    core.execute("INSERT INTO publish_state (event_id, updated_at) VALUES ('E1', now())")
    core.execute(
        "INSERT INTO extraction (source, purpose, request_url, requested_at, outcome)"
        " VALUES ('usgs_feed', 'live', 'https://example.org', now(), 'ok')"
    )


@pytest.mark.parametrize("role", ["writer", "reader"])
def test_both_roles_read_the_dimensions(connect, role: str) -> None:
    conn = connect(role)
    assert conn.execute("SELECT count(*) FROM dim_country").fetchone()[0] == 177
    assert conn.execute("SELECT count(*) FROM dim_date").fetchone()[0] > 0
