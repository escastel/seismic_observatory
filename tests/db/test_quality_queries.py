"""Known-data tests for db/queries/quality.sql (spec 004, T019-T020).

Every named query in the file runs against a small, fully known set of messages.
The counts are checked one by one, and synthetic rows must stay out of the
default queries and show up only in the "-synthetic-only" variants.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
import pytest
from psycopg.types.json import Jsonb
from tests.db.helpers import MESSAGE_LOG_SQL, Message, Version, process_message, quarantine, utc

REPO_ROOT = Path(__file__).resolve().parents[2]
QUALITY_SQL = REPO_ROOT / "db" / "queries" / "quality.sql"

REPROCESS_LOG_SQL = """
INSERT INTO message_log (kafka_topic, kafka_partition, kafka_offset, attempt, event_id, updated_at, outcome, produced_at)
VALUES (%s, %s, %s, 1, %s, %s, %s, %s)
ON CONFLICT (kafka_topic, kafka_partition, kafka_offset, attempt) DO NOTHING
"""

EXPECTED_NAMES = {
    "messages-by-outcome",
    "messages-by-outcome-synthetic-only",
    "reprocessed-by-outcome",
    "reprocessed-by-outcome-synthetic-only",
    "received-check",
    "quarantine-by-reason",
    "quarantine-by-reason-synthetic-only",
    "quarantined-messages",
    "quarantined-messages-synthetic-only",
    "events-by-flag",
    "events-by-flag-synthetic-only",
    "completeness",
    "completeness-synthetic-only",
    "versions-vs-messages",
    "duplicated-versions",
    "current-uniqueness",
    "invalid-coordinates",
    "updated-before-event",
    "country-missing-entity",
    "delays-updated-minutes",
    "delays-ingested-minutes",
    "excluded-events-by-type",
}


def load_queries() -> dict[str, str]:
    """Split quality.sql on its '-- name:' markers; the header before the first one is ignored."""
    text = QUALITY_SQL.read_text(encoding="utf-8")
    queries: dict[str, str] = {}
    for part in re.split(r"^-- name: ", text, flags=re.MULTILINE)[1:]:
        slug, _, body = part.partition("\n")
        slug = slug.strip()
        assert slug not in queries, f"duplicate query name {slug}"
        queries[slug] = body
    return queries


QUERIES = load_queries()


def rows_of(conn: psycopg.Connection, name: str) -> list[dict[str, Any]]:
    """Run a named query and return its rows as dictionaries."""
    cursor = conn.execute(QUERIES[name])
    columns = [column.name for column in cursor.description or []]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def one_row(conn: psycopg.Connection, name: str) -> dict[str, Any]:
    rows = rows_of(conn, name)
    assert len(rows) == 1, f"{name} returned {len(rows)} rows"
    return rows[0]


def log_message(
    conn: psycopg.Connection,
    message: Message,
    outcome: str,
    event_id: str | None = None,
    updated_at: datetime | None = None,
) -> None:
    conn.execute(
        MESSAGE_LOG_SQL,
        (message.topic, message.partition, message.offset, event_id, updated_at, outcome, None),
    )


def build_known_data(conn: psycopg.Connection) -> None:
    """Messages 0-6 are real, 7-8 synthetic. Expected results are asserted in the tests below.

    0 new        E1 10:05 magnitude 4.2
    1 new        E2 10:12 without magnitude, mag_type, place or country (completeness)
    2 revised    E1 10:09 magnitude 4.6, flag depth_from_text
    3 duplicate  E1 10:05 again
    4 stale      E1 10:07, earlier than the current version and never seen
    5 excluded   X1, a quarry blast (excluded_event)
    6 quarantined, two reason codes (missing_time, invalid_updated), event Q1
    7 quarantined, synthetic, malformed JSON, no event id
    8 new        S1, synthetic event carrying the flag synthetic
    """
    msg = [Message("earthquakes.live", 0, offset) for offset in range(9)]

    assert process_message(conn, msg[0], Version("E1", utc("2026-11-14 10:05"), magnitude=4.2)) == "new"
    assert (
        process_message(
            conn,
            msg[1],
            Version("E2", utc("2026-11-14 10:12"), magnitude=None, mag_type=None, place=None, country_id=None),
        )
        == "new"
    )
    assert (
        process_message(
            conn,
            msg[2],
            Version("E1", utc("2026-11-14 10:09"), magnitude=4.6, quality_flags=["depth_from_text"]),
        )
        == "revised"
    )
    assert process_message(conn, msg[3], Version("E1", utc("2026-11-14 10:05"), magnitude=4.2)) == "duplicate"
    assert process_message(conn, msg[4], Version("E1", utc("2026-11-14 10:07"), magnitude=4.4)) == "stale"

    conn.execute(
        """
        INSERT INTO excluded_event (event_id, updated_at, event_type, payload)
        VALUES ('X1', %s, 'quarry blast', %s)
        """,
        (utc("2026-11-14 10:03"), Jsonb({"id": "X1"})),
    )
    log_message(conn, msg[5], "excluded", "X1", utc("2026-11-14 10:03"))

    assert (
        process_message(
            conn,
            msg[6],
            {"reason_codes": ["missing_time", "invalid_updated"], "event_id": "Q1", "payload": {"id": "Q1"}},
        )
        == "quarantined"
    )

    quarantine(conn, msg[7], ["malformed_json"], raw_text="{not json", is_synthetic=True)
    log_message(conn, msg[7], "quarantined")

    assert process_message(conn, msg[8], Version("S1", utc("2026-11-14 10:20"), quality_flags=["synthetic"])) == "new"

    # Reprocessing attempts (attempt = 1): both still rejected.
    for message, event_id in ((msg[6], "Q1"), (msg[7], None)):
        conn.execute(
            REPROCESS_LOG_SQL,
            (message.topic, message.partition, message.offset, event_id, None, "quarantined", None),
        )


@pytest.fixture
def known(owner_conn: psycopg.Connection) -> psycopg.Connection:
    build_known_data(owner_conn)
    return owner_conn


def test_query_file_has_every_named_query() -> None:
    assert set(QUERIES) == EXPECTED_NAMES


def test_messages_by_outcome_counts_attempt_zero_only(known: psycopg.Connection) -> None:
    rows = {row["outcome"]: row["messages"] for row in rows_of(known, "messages-by-outcome")}
    assert rows == {"new": 2, "revised": 1, "stale": 1, "duplicate": 1, "excluded": 1, "quarantined": 1}


def test_messages_by_outcome_synthetic_only(known: psycopg.Connection) -> None:
    rows = {row["outcome"]: row["messages"] for row in rows_of(known, "messages-by-outcome-synthetic-only")}
    assert rows == {"new": 1, "quarantined": 1}


def test_reprocessed_rows_are_counted_apart(known: psycopg.Connection) -> None:
    real = {row["outcome"]: row["messages"] for row in rows_of(known, "reprocessed-by-outcome")}
    synthetic = {row["outcome"]: row["messages"] for row in rows_of(known, "reprocessed-by-outcome-synthetic-only")}
    assert real == {"quarantined": 1}
    assert synthetic == {"quarantined": 1}


def test_received_sum_has_zero_difference(known: psycopg.Connection) -> None:
    row = one_row(known, "received-check")
    assert row["received"] == 7
    assert row["sum_of_outcomes"] == 7
    assert row["difference"] == 0


def test_quarantine_by_reason_counts_two_reason_message_in_both(known: psycopg.Connection) -> None:
    rows = {row["reason"]: row["messages"] for row in rows_of(known, "quarantine-by-reason")}
    assert rows == {"missing_time": 1, "invalid_updated": 1}


def test_quarantine_by_reason_synthetic_only(known: psycopg.Connection) -> None:
    rows = {row["reason"]: row["messages"] for row in rows_of(known, "quarantine-by-reason-synthetic-only")}
    assert rows == {"malformed_json": 1}


def test_two_reason_message_counts_once_as_rejected(known: psycopg.Connection) -> None:
    row = one_row(known, "quarantined-messages")
    assert row["rejected_messages"] == 1
    assert row["quarantine_rows"] == 1
    assert row["reason_entries"] == 2


def test_quarantined_messages_synthetic_only(known: psycopg.Connection) -> None:
    row = one_row(known, "quarantined-messages-synthetic-only")
    assert row["rejected_messages"] == 1
    assert row["reason_entries"] == 1


def test_events_by_flag_excludes_synthetic(known: psycopg.Connection) -> None:
    rows = {row["flag"]: row["events"] for row in rows_of(known, "events-by-flag")}
    assert rows == {"depth_from_text": 1}


def test_events_by_flag_synthetic_only(known: psycopg.Connection) -> None:
    rows = {row["flag"]: row["events"] for row in rows_of(known, "events-by-flag-synthetic-only")}
    assert rows == {"synthetic": 1}


def test_completeness_over_real_current_earthquakes(known: psycopg.Connection) -> None:
    row = one_row(known, "completeness")
    assert row["current_earthquakes"] == 2
    assert row["magnitude_not_null"] == 1
    assert row["magnitude_pct"] == pytest.approx(50.0)
    assert row["mag_type_not_null"] == 1
    assert row["mag_type_pct"] == pytest.approx(50.0)
    assert row["depth_km_not_null"] == 2
    assert row["depth_km_pct"] == pytest.approx(100.0)
    assert row["place_not_null"] == 1
    assert row["place_pct"] == pytest.approx(50.0)
    assert row["country_id_not_null"] == 1
    assert row["country_id_pct"] == pytest.approx(50.0)


def test_completeness_synthetic_only(known: psycopg.Connection) -> None:
    row = one_row(known, "completeness-synthetic-only")
    assert row["current_earthquakes"] == 1
    assert row["magnitude_pct"] == pytest.approx(100.0)


def test_versions_match_messages_that_add_a_version(known: psycopg.Connection) -> None:
    row = one_row(known, "versions-vs-messages")
    # E1 10:05, E1 10:09, E1 10:07 and E2 10:12; messages new, revised and stale on real events.
    assert row["distinct_versions"] == 4
    assert row["version_messages"] == 4
    assert row["difference"] == 0


@pytest.mark.parametrize(
    ("name", "column"),
    [
        ("duplicated-versions", "duplicated_versions"),
        ("current-uniqueness", "duplicated_event_ids"),
        ("invalid-coordinates", "invalid_coordinates"),
        ("updated-before-event", "updated_before_event"),
        ("country-missing-entity", "missing_countries"),
    ],
)
def test_integrity_checks_are_zero(known: psycopg.Connection, name: str, column: str) -> None:
    assert one_row(known, name)[column] == 0


def test_delays_to_update_in_minutes(known: psycopg.Connection) -> None:
    row = one_row(known, "delays-updated-minutes")
    # E1 updated at 10:09 and E2 at 10:12, both with event_time 10:00: 9 and 12 minutes.
    assert row["current_earthquakes"] == 2
    assert row["median_minutes"] == pytest.approx(10.5)
    assert row["p95_minutes"] == pytest.approx(11.85)


def test_delays_to_ingestion_are_present(known: psycopg.Connection) -> None:
    row = one_row(known, "delays-ingested-minutes")
    assert row["current_earthquakes"] == 2
    assert row["median_minutes"] is not None
    assert row["p95_minutes"] is not None


def test_excluded_events_by_type(known: psycopg.Connection) -> None:
    rows = rows_of(known, "excluded-events-by-type")
    assert rows == [{"event_type": "quarry blast", "events": 1, "versions": 1}]


def test_synthetic_rows_stay_out_of_default_queries(known: psycopg.Connection) -> None:
    # S1 and the synthetic quarantine row (message 7) appear only in the synthetic-only variants.
    outcomes = {row["outcome"] for row in rows_of(known, "messages-by-outcome")}
    assert "new" in outcomes
    assert one_row(known, "completeness")["current_earthquakes"] == 2
    assert one_row(known, "quarantined-messages")["rejected_messages"] == 1
    assert one_row(known, "received-check")["received"] == 7


def test_query_file_runs_every_query(known: psycopg.Connection) -> None:
    for name in QUERIES:
        rows_of(known, name)
