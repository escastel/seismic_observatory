"""Extractions, raw payloads, rejections, exclusions and the message log (FR-014, FR-015, FR-019)."""

from __future__ import annotations

import gzip

import psycopg
import pytest
from psycopg.types.json import Jsonb

from tests.db.helpers import Message, count, faq12_sequence, process_message, quarantine, utc

FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"

EXTRACTION_SQL = """
INSERT INTO extraction (source, purpose, request_url, requested_at, duration_ms, attempt_count,
                        http_status, outcome, error_detail, record_count, content_sha256)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
RETURNING extraction_id
"""

RAW_PAYLOAD_SQL = """
INSERT INTO raw_payload (content_sha256, encoding, body, file_path, byte_size, first_seen_at, last_seen_at)
VALUES (%(sha)s, %(encoding)s, %(body)s, %(file_path)s, %(size)s, %(seen)s, %(seen)s)
ON CONFLICT (content_sha256) DO UPDATE SET last_seen_at = EXCLUDED.last_seen_at
"""


def extraction(conn, *, outcome="ok", sha=None, purpose="live", http_status=200, error_detail=None, at="2026-11-14 10:00"):
    return conn.execute(
        EXTRACTION_SQL,
        ("usgs_feed", purpose, FEED_URL, utc(at), 420, 1, http_status, outcome, error_detail, 3, sha),
    ).fetchone()[0]


def raw_payload(conn, sha, *, seen, body=b'{"features":[]}', file_path=None):
    conn.execute(
        RAW_PAYLOAD_SQL,
        {
            "sha": sha,
            "encoding": "gzip" if body is not None else "file",
            "body": gzip.compress(body) if body is not None else None,
            "file_path": file_path,
            "size": len(body) if body is not None else 1_000_000,
            "seen": utc(seen),
        },
    )


def test_identical_content_is_stored_once(writer_conn: psycopg.Connection) -> None:
    for at in ("2026-11-14 10:00", "2026-11-14 10:01"):
        extraction(writer_conn, sha="abc", at=at)
        raw_payload(writer_conn, "abc", seen=at)

    assert count(writer_conn, "extraction") == 2
    assert count(writer_conn, "raw_payload") == 1
    first, last = writer_conn.execute("SELECT first_seen_at, last_seen_at FROM raw_payload").fetchone()
    assert (first, last) == (utc("2026-11-14 10:00"), utc("2026-11-14 10:01"))


def test_failed_extraction_is_recorded_without_fingerprint(writer_conn: psycopg.Connection) -> None:
    extraction(writer_conn, outcome="timeout", http_status=None, error_detail="read timed out after 30 s")
    row = writer_conn.execute("SELECT outcome, error_detail, content_sha256, http_status FROM extraction").fetchone()
    assert row == ("timeout", "read timed out after 30 s", None, None)


@pytest.mark.parametrize(("outcome", "purpose"), [("unknown", "live"), ("ok", "backfill")])
def test_extraction_values_are_closed(writer_conn: psycopg.Connection, outcome: str, purpose: str) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        extraction(writer_conn, outcome=outcome, purpose=purpose)


def test_raw_payload_needs_a_body_or_a_file(writer_conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        writer_conn.execute(
            "INSERT INTO raw_payload (content_sha256, encoding, byte_size) VALUES ('x', 'gzip', 10)"
        )


def test_purge_removes_only_old_bodies(writer_conn: psycopg.Connection) -> None:
    writer_conn.execute(
        "INSERT INTO raw_payload (content_sha256, encoding, body, byte_size, first_seen_at, last_seen_at)"
        " VALUES ('old', 'gzip', '\\x00', 1, now() - interval '9 days', now() - interval '8 days'),"
        "        ('recent', 'gzip', '\\x00', 1, now() - interval '9 days', now() - interval '6 days')"
    )
    writer_conn.execute(
        "INSERT INTO raw_payload (content_sha256, encoding, file_path, byte_size, first_seen_at, last_seen_at)"
        " VALUES ('catalog', 'file', 'data/catalog/2025.geojson', 1, now() - interval '400 days', now() - interval '400 days')"
    )
    extraction(writer_conn, sha="old")
    extraction(writer_conn, sha="catalog")

    assert writer_conn.execute("SELECT core.purge_raw_payload(7)").fetchone()[0] == 1

    remaining = {sha for (sha,) in writer_conn.execute("SELECT content_sha256 FROM raw_payload").fetchall()}
    assert remaining == {"recent", "catalog"}
    assert count(writer_conn, "extraction") == 2
    assert writer_conn.execute("SELECT core.purge_raw_payload(7)").fetchone()[0] == 0


def test_quarantine_keeps_one_row_per_message(writer_conn: psycopg.Connection) -> None:
    message = Message("earthquakes.live", 0, 42)
    quarantine(writer_conn, message, ["missing_time", "invalid_coordinates"], payload={"id": "E1"})
    quarantine(writer_conn, message, ["missing_time"], payload={"id": "E1"})

    assert count(writer_conn, "quarantine") == 1
    assert writer_conn.execute("SELECT reason_codes FROM quarantine").fetchone()[0] == [
        "missing_time",
        "invalid_coordinates",
    ]
    with pytest.raises(psycopg.errors.UniqueViolation):
        writer_conn.execute(
            "INSERT INTO quarantine (kafka_topic, kafka_partition, kafka_offset, reason_codes, reason_detail, raw_text)"
            " VALUES ('earthquakes.live', 0, 42, '{x}', 'again', 'x')"
        )


def test_quarantine_needs_the_original_message(writer_conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        quarantine(writer_conn, Message("earthquakes.live", 0, 1), ["invalid_json"])


def test_quarantine_needs_a_reason(writer_conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        quarantine(writer_conn, Message("earthquakes.live", 0, 1), [], raw_text="{")


def test_non_json_message_is_kept_as_text(writer_conn: psycopg.Connection) -> None:
    quarantine(writer_conn, Message("earthquakes.live", 0, 1), ["invalid_json"], raw_text="{not json", is_synthetic=True)
    assert writer_conn.execute("SELECT payload, raw_text, is_synthetic FROM quarantine").fetchone() == (
        None,
        "{not json",
        True,
    )


EXCLUDED_SQL = """
INSERT INTO excluded_event (event_id, updated_at, event_type, extraction_id, payload)
VALUES (%s, %s, %s, %s, %s)
"""


def test_excluded_event_is_one_row_per_version(writer_conn: psycopg.Connection) -> None:
    extraction_id = extraction(writer_conn)
    args = ("Q1", utc("2026-11-14 10:05"), "quarry blast", extraction_id, Jsonb({"id": "Q1"}))
    writer_conn.execute(EXCLUDED_SQL, args)

    row = writer_conn.execute("SELECT event_type, reason_code, extraction_id FROM excluded_event").fetchone()
    assert row == ("quarry blast", "not_earthquake", extraction_id)
    with pytest.raises(psycopg.errors.UniqueViolation):
        writer_conn.execute(EXCLUDED_SQL, args)


def test_excluded_event_needs_an_existing_extraction(writer_conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        writer_conn.execute(EXCLUDED_SQL, ("Q1", utc("2026-11-14 10:05"), "explosion", 999_999, Jsonb({})))


def test_message_log_outcomes_are_closed(writer_conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        writer_conn.execute(
            "INSERT INTO message_log (kafka_topic, kafka_partition, kafka_offset, outcome) VALUES ('t', 0, 0, 'ignored')"
        )


def test_message_log_gives_the_denominators_of_faq12(writer_conn: psycopg.Connection) -> None:
    produced = utc("2026-11-14 10:10")
    for message, version in faq12_sequence():
        process_message(writer_conn, message, version, produced_at=produced)

    outcomes = dict(writer_conn.execute("SELECT outcome, count(*) FROM message_log GROUP BY outcome").fetchall())
    assert count(writer_conn, "message_log") == 5
    assert outcomes == {"new": 2, "revised": 1, "duplicate": 2}
    assert count(writer_conn, "event_version") == 3
    assert count(writer_conn, "event_current") == 2
    lag_ok = writer_conn.execute("SELECT bool_and(processed_at >= produced_at) FROM message_log").fetchone()[0]
    assert lag_ok is True
