"""Secondary indexes kept by the measurement (db/sql/060_indexes.sql, FR-026)."""

from __future__ import annotations

import psycopg

EVENT_INDEXES = {
    "event_current_event_time_idx",
    "event_current_country_event_time_idx",
    "event_current_magnitude_event_time_idx",
}


def secondary_indexes(conn: psycopg.Connection, schema: str) -> set[str]:
    rows = conn.execute(
        """
        SELECT i.indexname
        FROM pg_indexes i
        JOIN pg_class c ON c.relname = i.indexname
        JOIN pg_index x ON x.indexrelid = c.oid
        WHERE i.schemaname = %s AND NOT x.indisprimary AND NOT x.indisunique
        """,
        (schema,),
    ).fetchall()
    return {name for (name,) in rows}


def test_core_has_the_measured_indexes(owner_conn: psycopg.Connection) -> None:
    assert secondary_indexes(owner_conn, "core") == EVENT_INDEXES | {"extraction_last_ok_feed_idx"}


def test_replay_has_the_same_event_indexes(owner_conn: psycopg.Connection) -> None:
    assert secondary_indexes(owner_conn, "replay") == EVENT_INDEXES


def test_last_ingestion_uses_the_partial_index(owner_conn: psycopg.Connection) -> None:
    owner_conn.execute("SET enable_seqscan = off")
    plan = owner_conn.execute(
        "EXPLAIN SELECT max(requested_at) FROM core.extraction"
        " WHERE source = 'usgs_feed' AND outcome IN ('ok', 'not_modified')"
    ).fetchall()
    assert any("extraction_last_ok_feed_idx" in line for (line,) in plan)
