"""Provenance written by the ingestion (FR-001 to FR-006, FR-010, FR-014; data-model.md §2–§4)."""

from __future__ import annotations

import gzip
import json
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from producer.app import provenance
from producer.app.classify import classify
from producer.app.provenance import Counts
from producer.app.usgs import FetchResult
from tests.db.async_support import run_with_conn
from tests.support.usgs_stub import collection, feature

NOW = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)
FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"


def result(outcome: str = "ok", *, payload=None, body: bytes | None = None, status: int | None = 200,
           detail: str | None = None, at: datetime = NOW, attempts: int = 1) -> FetchResult:
    if payload is not None and body is None:
        body = json.dumps(payload).encode()
    return FetchResult(
        url=FEED_URL, requested_at=at, outcome=outcome, http_status=status, attempt_count=attempts,
        duration_ms=180, body=body, payload=payload if outcome == "ok" else None, error_detail=detail,
        last_modified=None,
    )


def extraction_rows(owner_conn: psycopg.Connection) -> list[dict]:
    cursor = owner_conn.execute("SELECT * FROM core.extraction ORDER BY extraction_id")
    names = [column.name for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


@pytest.mark.parametrize(
    ("outcome", "status", "detail"),
    [
        ("http_error", 503, "HTTP 503: busy"),
        ("http_error", 429, "HTTP 429 (Retry-After 300 s)"),
        ("timeout", None, "timeout after 30 s"),
        ("invalid_json", 200, "response is not JSON"),
        ("invalid_structure", 200, "FeatureCollection without a 'features' list"),
    ],
)
def test_failed_requests_are_recorded_without_counts(test_database, owner_conn, outcome, status, detail) -> None:
    async def body(conn):
        return await provenance.record_extraction(
            conn, result(outcome, status=status, detail=detail, attempts=4), source="usgs_feed", purpose="live"
        )

    extraction_id = run_with_conn(test_database, body)

    row = extraction_rows(owner_conn)[0]
    assert row["extraction_id"] == extraction_id
    assert (row["outcome"], row["http_status"], row["error_detail"], row["attempt_count"]) == (outcome, status, detail, 4)
    assert (row["record_count"], row["earthquake_count"], row["excluded_count"], row["published_count"]) == (None,) * 4
    assert row["source_generated_at"] is None
    assert row["requested_at"] == NOW and row["duration_ms"] == 180 and row["request_url"] == FEED_URL


def test_successful_request_keeps_counts_metadata_and_detail(test_database, owner_conn) -> None:
    payload = collection([feature("E1"), feature("Q1", event_type="quarry blast"), feature(None)], generated=1794705713000)
    split = classify(payload["features"])

    async def body(conn):
        extraction_id = await provenance.record_extraction(
            conn,
            result(payload=payload),
            source="usgs_feed",
            purpose="live",
            counts=Counts(split.received, len(split.earthquakes), split.excluded_count),
            fingerprint="abc",
            extra_detail=split.unidentifiable_detail(),
        )
        await provenance.set_published_count(conn, extraction_id, 1)

    run_with_conn(test_database, body)

    row = extraction_rows(owner_conn)[0]
    assert (row["record_count"], row["earthquake_count"], row["excluded_count"], row["published_count"]) == (3, 1, 2, 1)
    assert row["record_count"] == row["earthquake_count"] + row["excluded_count"]
    assert row["source_generated_at"] == datetime(2026, 11, 15, 1, 21, 53, tzinfo=timezone.utc)
    assert row["content_sha256"] == "abc"
    assert "#2: no id" in row["error_detail"]


def test_catalog_request_keeps_parameters_and_window(test_database, owner_conn) -> None:
    window = (datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2025, 2, 1, tzinfo=timezone.utc))
    params = {"endpoint": "count", "starttime": "2025-01-01T00:00:00Z", "minmagnitude": 4}

    run_with_conn(test_database, lambda conn: provenance.record_extraction(
        conn, result(payload={"count": 1413, "maxAllowed": 20000}), source="usgs_catalog",
        purpose="historical_load", counts=Counts(record=1413), request_params=params, window=window))

    row = extraction_rows(owner_conn)[0]
    assert row["request_params"] == params
    assert (row["window_start"], row["window_end"]) == window
    assert row["record_count"] == 1413 and row["earthquake_count"] is None


def test_unknown_purpose_is_refused_before_the_database() -> None:
    import asyncio

    with pytest.raises(ValueError, match="purpose"):
        asyncio.run(provenance.record_extraction(None, result(), source="usgs_feed", purpose="backfill"))


def test_same_content_is_stored_once(test_database, owner_conn) -> None:
    body = b'{"type":"FeatureCollection","features":[]}'
    later = NOW + timedelta(minutes=5)

    async def run(conn):
        await provenance.store_body(conn, "sha-1", body, seen_at=NOW)
        await provenance.store_body(conn, "sha-1", body, seen_at=later)

    run_with_conn(test_database, run)

    rows = owner_conn.execute(
        "SELECT encoding, body, byte_size, first_seen_at, last_seen_at, file_path FROM core.raw_payload"
    ).fetchall()
    assert len(rows) == 1
    encoding, stored, size, first, last, path = rows[0]
    assert (encoding, size, first, last, path) == ("gzip", len(body), NOW, later, None)
    assert gzip.decompress(stored) == body


def test_last_seen_never_moves_back(test_database, owner_conn) -> None:
    async def run(conn):
        await provenance.store_body(conn, "sha-1", b"{}", seen_at=NOW)
        await provenance.store_body(conn, "sha-1", b"{}", seen_at=NOW - timedelta(days=1))

    run_with_conn(test_database, run)
    assert owner_conn.execute("SELECT last_seen_at FROM core.raw_payload").fetchone()[0] == NOW


def test_not_modified_touches_the_last_content(test_database, owner_conn) -> None:
    later = NOW + timedelta(minutes=1)

    async def run(conn):
        await provenance.store_body(conn, "sha-1", b"{}", seen_at=NOW)
        return await provenance.touch_payload(conn, "sha-1", seen_at=later), await provenance.touch_payload(conn, "nope")

    touched, missing = run_with_conn(test_database, run)
    assert (touched, missing) == (True, False)
    assert owner_conn.execute("SELECT last_seen_at FROM core.raw_payload").fetchone()[0] == later


def test_catalog_file_reference(test_database, owner_conn) -> None:
    run_with_conn(test_database, lambda conn: provenance.store_file(
        conn, "sha-file", "usgs/catalog/2025-01-01T000000Z_2025-02-01T000000Z_m4_earthquake.geojson", 2_345_678))

    row = owner_conn.execute("SELECT encoding, body, file_path, byte_size FROM core.raw_payload").fetchone()
    assert row == ("file", None, "usgs/catalog/2025-01-01T000000Z_2025-02-01T000000Z_m4_earthquake.geojson", 2_345_678)


def test_exclusions_are_stored_once_with_their_first_extraction(test_database, owner_conn) -> None:
    split = classify([feature("Q1", event_type="quarry blast"), feature("X1", event_type=None), feature("E1")])

    async def run(conn):
        first = await provenance.record_extraction(conn, result(payload={}), source="usgs_feed", purpose="live")
        second = await provenance.record_extraction(conn, result(payload={}), source="usgs_feed", purpose="live")
        inserted = [await provenance.record_exclusions(conn, split.excluded, first),
                    await provenance.record_exclusions(conn, split.excluded, second)]
        return first, inserted

    first, inserted = run_with_conn(test_database, run)

    assert inserted == [2, 0]
    rows = owner_conn.execute(
        "SELECT event_id, event_type, reason_code, extraction_id, payload ->> 'id' FROM core.excluded_event ORDER BY 1"
    ).fetchall()
    assert rows == [("Q1", "quarry blast", "not_earthquake", first, "Q1"), ("X1", None, "missing_type", first, "X1")]


def test_last_successful_feed_request(test_database) -> None:
    async def run(conn):
        empty = await provenance.last_successful_feed_request(conn)
        await provenance.record_extraction(conn, result(payload={}, at=NOW), source="usgs_feed", purpose="live")
        await provenance.record_extraction(conn, result("not_modified", status=304, at=NOW + timedelta(minutes=1)),
                                           source="usgs_feed", purpose="live")
        await provenance.record_extraction(conn, result("timeout", status=None, at=NOW + timedelta(minutes=2)),
                                           source="usgs_feed", purpose="live")
        await provenance.record_extraction(conn, result(payload={}, at=NOW + timedelta(minutes=3)),
                                           source="usgs_catalog", purpose="historical_load")
        return empty, await provenance.last_successful_feed_request(conn)

    empty, last = run_with_conn(test_database, run)
    assert empty is None
    assert last == NOW + timedelta(minutes=1)


def insert_feed_requests(owner_conn, moments, outcome="ok") -> None:
    for moment in moments:
        owner_conn.execute(
            "INSERT INTO core.extraction (source, purpose, request_url, requested_at, outcome) "
            "VALUES ('usgs_feed', 'live', %s, %s, %s)", (FEED_URL, moment, outcome))


def test_gaps_are_detected_from_the_feed_history_and_recovered(test_database, owner_conn) -> None:
    from producer.app.gaps import detect

    hour = timedelta(hours=1)
    first_run = [NOW - 100 * hour + n * hour for n in range(10)]           # 10 hourly requests
    second_run = [NOW - 54 * hour + n * hour for n in range(5)]            # 36 h after the first run ends
    third_run = [NOW - 20 * hour + n * hour for n in range(20)]            # 29 h after the second ends
    insert_feed_requests(owner_conn, first_run + second_run + third_run)
    insert_feed_requests(owner_conn, [NOW - 70 * hour], outcome="timeout")  # failures do not close a gap

    def found():
        return run_with_conn(test_database, lambda conn: detect(conn, NOW, timedelta(minutes=60)))

    gaps = found()
    assert [(gap.last_before, gap.next_after, covered) for gap, covered in gaps] == [
        (first_run[-1], second_run[0], False),
        (second_run[-1], third_run[0], False),
    ]
    first = gaps[0][0]
    assert first.start == first_run[-1] - hour and first.end == second_run[0] - 24 * hour + hour

    owner_conn.execute(
        "INSERT INTO core.extraction (source, purpose, request_url, requested_at, outcome, request_params, "
        "window_start, window_end) VALUES ('usgs_catalog', 'gap_recovery', 'x', %s, 'ok', "
        "'{\"endpoint\": \"query\"}', %s, %s)", (NOW, first.start, first.end))
    assert [covered for _, covered in found()] == [True, False]


def test_open_gap_when_the_feed_stopped(test_database, owner_conn) -> None:
    from producer.app.gaps import open_gap

    insert_feed_requests(owner_conn, [NOW - timedelta(hours=36)])
    gap = run_with_conn(test_database, lambda conn: open_gap(conn, NOW, timedelta(minutes=60)))
    assert gap is not None and gap.next_after is None
    assert gap.end == NOW - timedelta(hours=23)
