"""The replay schema can never alter or mix with real data (FR-012, FR-013, principle VI)."""

from __future__ import annotations

from datetime import timedelta

import psycopg
import pytest

from tests.db.helpers import PUBLISH_STATE_SQL, Message, Version, apply_version, process_message, utc

REPLAYED_AT = utc("2026-11-14 12:00")
CORE_TABLES = ("event_current", "event_version", "publish_state", "message_log")


def fingerprint(conn: psycopg.Connection, schema: str, table: str) -> tuple[int, str]:
    """Row count and an order-independent checksum of every column of a table."""
    row = conn.execute(
        f"SELECT count(*), coalesce(md5(string_agg(t::text, '|' ORDER BY t::text)), '') FROM {schema}.{table} t"  # noqa: S608
    ).fetchone()
    assert row is not None
    return row[0], row[1]


@pytest.fixture
def core_conn(connect) -> psycopg.Connection:
    return connect("writer", search_path="core")


@pytest.fixture
def replay_conn(connect) -> psycopg.Connection:
    return connect("writer", search_path="replay, core")


def test_same_event_keeps_its_own_values_in_each_schema(core_conn, replay_conn) -> None:
    apply_version(core_conn, Version("E1", utc("2026-11-14 10:05"), magnitude=4.2))
    apply_version(replay_conn, Version("E1", utc("2026-11-14 10:09"), magnitude=6.1), replayed_at=REPLAYED_AT)

    assert core_conn.execute("SELECT magnitude FROM event_current WHERE event_id = 'E1'").fetchone()[0] == 4.2
    assert replay_conn.execute("SELECT magnitude FROM event_current WHERE event_id = 'E1'").fetchone()[0] == 6.1
    assert core_conn.execute("SELECT count(*) FROM core.event_version").fetchone()[0] == 1


def test_replay_load_and_reset_leave_core_untouched(owner_conn, core_conn, replay_conn) -> None:
    for n in range(20):
        version = Version(f"C{n}", utc("2026-11-14 10:00") + timedelta(minutes=n))
        process_message(core_conn, Message("earthquakes.live", 0, n), version, produced_at=version.updated_at)
        core_conn.execute(PUBLISH_STATE_SQL, (version.event_id, version.updated_at))
    before = {table: fingerprint(owner_conn, "core", table) for table in CORE_TABLES}
    dimensions_before = {table: fingerprint(owner_conn, "core", table) for table in ("dim_country", "dim_date")}

    base = utc("2025-01-01")
    with replay_conn.transaction():
        for n in range(10_000):
            # Event ids overlap with core on purpose: C0..C19 exist in both schemas.
            version = Version(f"C{n}", base + timedelta(minutes=n), event_time=base + timedelta(minutes=n))
            apply_version(replay_conn, version, Message("earthquakes.replay", 0, n), replayed_at=REPLAYED_AT)
    assert replay_conn.execute("SELECT count(*) FROM event_current").fetchone()[0] == 10_000
    assert {table: fingerprint(owner_conn, "core", table) for table in CORE_TABLES} == before

    replay_conn.execute("SELECT replay.reset()")

    for table in ("event_current", "event_version", "quarantine", "excluded_event", "publish_state", "message_log"):
        assert replay_conn.execute(f"SELECT count(*) FROM replay.{table}").fetchone()[0] == 0  # noqa: S608
    assert {table: fingerprint(owner_conn, "core", table) for table in CORE_TABLES} == before
    assert {table: fingerprint(owner_conn, "core", table) for table in ("dim_country", "dim_date")} == dimensions_before


def test_replayed_event_keeps_its_original_time(replay_conn) -> None:
    original = utc("2025-03-02 04:15")
    apply_version(replay_conn, Version("E1", utc("2025-03-02 04:30"), event_time=original), replayed_at=REPLAYED_AT)

    row = replay_conn.execute("SELECT event_time, event_date, replayed_at FROM event_current").fetchone()
    assert row[0] == original
    assert str(row[1]) == "2025-03-02"
    assert row[2] == REPLAYED_AT


def test_writer_can_reset_replay(replay_conn) -> None:
    apply_version(replay_conn, Version("E1", utc("2026-11-14 10:05")), replayed_at=REPLAYED_AT)
    replay_conn.execute("SELECT replay.reset()")
    assert replay_conn.execute("SELECT count(*) FROM event_current").fetchone()[0] == 0


def test_reader_cannot_reset_replay(reader_conn) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        reader_conn.execute("SELECT replay.reset()")


def test_core_has_no_reset_function(owner_conn) -> None:
    functions = owner_conn.execute(
        """
        SELECT p.proname
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'core'
        ORDER BY p.proname
        """
    ).fetchall()
    assert [name for (name,) in functions] == ["apply_event_version", "purge_raw_payload"]
    with pytest.raises(psycopg.errors.UndefinedFunction):
        owner_conn.execute("SELECT core.reset()")
