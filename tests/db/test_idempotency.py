"""Reprocessing the same messages never changes the stored state (FR-005, principle II)."""

from __future__ import annotations

from datetime import timedelta

import psycopg

from tests.db.helpers import Message, Version, count, process_message, utc

PASSES = 1_000
TABLES = ("event_current", "event_version", "quarantine", "message_log")


def build_messages() -> list[tuple[Message, Version | dict]]:
    """50 messages: 30 first versions, 10 revisions, 5 repetitions and 5 rejections."""
    base = utc("2026-11-14 10:00")
    messages: list[tuple[Message, Version | dict]] = []

    def add(item: Version | dict, topic: str = "earthquakes.live") -> None:
        messages.append((Message(topic, 0, len(messages)), item))

    for n in range(30):
        add(Version(f"E{n:02d}", base + timedelta(minutes=n), magnitude=2.0 + n / 10))
    for n in range(10):
        add(Version(f"E{n:02d}", base + timedelta(minutes=n, seconds=30), magnitude=5.0), "earthquakes.catalog")
    for n in range(5):
        add(Version(f"E{n:02d}", base + timedelta(minutes=n), magnitude=2.0 + n / 10))
    for n in range(4):
        add({"reason_codes": ["missing_time"], "event_id": f"Q{n}", "payload": {"id": f"Q{n}"}})
    add({"reason_codes": ["invalid_json"], "raw_text": "{not json"})
    assert len(messages) == 50
    return messages


def snapshot(conn: psycopg.Connection) -> dict[str, int]:
    return {table: count(conn, table) for table in TABLES}


def current_state(conn: psycopg.Connection) -> list[tuple]:
    return conn.execute("SELECT event_id, updated_at, magnitude FROM event_current ORDER BY event_id").fetchall()


def test_thousand_passes_leave_the_first_pass_counts(writer_conn: psycopg.Connection) -> None:
    messages = build_messages()

    first_outcomes = [process_message(writer_conn, message, item) for message, item in messages]
    first_counts = snapshot(writer_conn)
    first_state = current_state(writer_conn)

    assert first_counts == {"event_current": 30, "event_version": 40, "quarantine": 5, "message_log": 50}
    assert first_outcomes.count("new") == 30
    assert first_outcomes.count("revised") == 10
    assert first_outcomes.count("duplicate") == 5
    assert first_outcomes.count("quarantined") == 5

    for _ in range(PASSES - 1):
        for message, item in messages:
            process_message(writer_conn, message, item)

    assert snapshot(writer_conn) == first_counts
    assert current_state(writer_conn) == first_state
