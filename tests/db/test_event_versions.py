"""Version rule of apply_event_version (FR-004, FR-005, FAQ 12)."""

from __future__ import annotations

import psycopg

from tests.db.helpers import (
    PUBLISH_STATE_SQL,
    Message,
    Version,
    apply_version,
    count,
    faq12_sequence,
    process_message,
    utc,
)


def test_faq12_sequence_outcomes_and_counts(writer_conn: psycopg.Connection) -> None:
    outcomes = [process_message(writer_conn, message, version) for message, version in faq12_sequence()]

    assert outcomes == ["new", "duplicate", "revised", "duplicate", "new"]
    assert count(writer_conn, "event_current") == 2
    assert count(writer_conn, "event_version") == 3
    magnitude = writer_conn.execute("SELECT magnitude FROM event_current WHERE event_id = 'E1'").fetchone()[0]
    assert magnitude == 4.6


def test_older_unseen_version_is_stale_and_only_joins_history(writer_conn: psycopg.Connection) -> None:
    assert apply_version(writer_conn, Version("E1", utc("2026-11-14 10:09"), magnitude=4.6)) == "new"

    outcome = apply_version(writer_conn, Version("E1", utc("2026-11-14 10:05"), magnitude=4.2), Message("t", 0, 1))

    assert outcome == "stale"
    assert count(writer_conn, "event_version") == 2
    current = writer_conn.execute("SELECT updated_at, magnitude FROM event_current WHERE event_id = 'E1'").fetchone()
    assert current == (utc("2026-11-14 10:09"), 4.6)


def test_revision_keeps_first_ingestion_and_moves_last_ingestion(writer_conn: psycopg.Connection) -> None:
    apply_version(writer_conn, Version("E1", utc("2026-11-14 10:05")))
    first_before, last_before = writer_conn.execute(
        "SELECT first_ingested_at, ingested_at FROM event_current WHERE event_id = 'E1'"
    ).fetchone()

    assert apply_version(writer_conn, Version("E1", utc("2026-11-14 10:09"), magnitude=4.6)) == "revised"

    first_after, last_after = writer_conn.execute(
        "SELECT first_ingested_at, ingested_at FROM event_current WHERE event_id = 'E1'"
    ).fetchone()
    assert first_after == first_before
    assert last_after > last_before


def test_revision_replaces_every_current_attribute(writer_conn: psycopg.Connection) -> None:
    apply_version(writer_conn, Version("E1", utc("2026-11-14 10:05")))
    revised = Version(
        "E1",
        utc("2026-11-14 10:09"),
        event_time=utc("2026-11-14 09:59"),
        magnitude=None,
        mag_type=None,
        longitude=2.17,
        latitude=41.38,
        depth_km=None,
        place=None,
        country_id=None,
        quality_flags=["negative_depth"],
        source="usgs_catalog",
    )
    apply_version(writer_conn, revised)

    row = writer_conn.execute(
        """
        SELECT source, event_time, magnitude, mag_type, longitude, latitude, depth_km,
               place, country_id, quality_flags
        FROM event_current WHERE event_id = 'E1'
        """
    ).fetchone()
    assert row == ("usgs_catalog", utc("2026-11-14 09:59"), None, None, 2.17, 41.38, None, None, None, ["negative_depth"])


def test_each_version_keeps_its_own_source_and_message(writer_conn: psycopg.Connection) -> None:
    apply_version(writer_conn, Version("E1", utc("2026-11-14 10:05"), source="usgs_feed"), Message("earthquakes.live", 0, 7))
    apply_version(
        writer_conn,
        Version("E1", utc("2026-11-14 10:09"), source="usgs_catalog"),
        Message("earthquakes.catalog", 0, 3),
    )

    rows = writer_conn.execute(
        "SELECT source, kafka_topic, kafka_offset, payload ->> 'id' FROM event_version ORDER BY updated_at"
    ).fetchall()
    assert rows == [("usgs_feed", "earthquakes.live", 7, "E1"), ("usgs_catalog", "earthquakes.catalog", 3, "E1")]


def test_duplicate_does_not_overwrite_the_first_message_reference(writer_conn: psycopg.Connection) -> None:
    version = Version("E1", utc("2026-11-14 10:05"))
    apply_version(writer_conn, version, Message("earthquakes.live", 0, 1))
    assert apply_version(writer_conn, version, Message("earthquakes.live", 0, 2)) == "duplicate"

    offset = writer_conn.execute("SELECT kafka_offset FROM event_version").fetchone()[0]
    assert offset == 1


def test_publish_state_never_moves_back(writer_conn: psycopg.Connection) -> None:
    writer_conn.execute(PUBLISH_STATE_SQL, ("E1", utc("2026-11-14 10:09")))
    writer_conn.execute(PUBLISH_STATE_SQL, ("E1", utc("2026-11-14 10:05")))
    assert writer_conn.execute("SELECT updated_at FROM publish_state").fetchone()[0] == utc("2026-11-14 10:09")

    writer_conn.execute(PUBLISH_STATE_SQL, ("E1", utc("2026-11-14 10:12")))
    assert writer_conn.execute("SELECT updated_at FROM publish_state").fetchone()[0] == utc("2026-11-14 10:12")
    assert count(writer_conn, "publish_state") == 1
