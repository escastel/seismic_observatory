"""One live feed cycle against the real model (US1: FR-001 to FR-014, FR-001a; quickstart V1, V2)."""

from __future__ import annotations

import gzip
import json
from datetime import datetime, timezone

import psycopg
import pytest

from common.settings import DatabaseSettings, KafkaSettings, ProducerSettings, TopicNames, UsgsSettings
from producer.app.main import FeedState, feed_cycle, seconds_until_next_cycle
from tests.db.async_support import run_with_pool
from tests.support.fake_kafka import FakeProducer
from tests.support.usgs_stub import FakeUsgs, Reply, collection, feature

FEED = "/feed"


def config(usgs: FakeUsgs, interval: int = 60) -> ProducerSettings:
    source = UsgsSettings(feed_url=usgs.url(FEED), catalog_url=usgs.catalog_url, timeout_seconds=2,
                          max_attempts=1, user_agent="observatory-test/1.0")
    return ProducerSettings(
        database=DatabaseSettings("unused", 5432, "unused", "unused", "unused"),
        kafka=KafkaSettings("unused", TopicNames(), 168),
        feed_url=source.feed_url,
        interval_seconds=interval,
        raw_payload_retention_days=7,
        usgs=source,
        gap_margin_minutes=60,
    )


def cycles(test_database: str, usgs: FakeUsgs, producer: FakeProducer, count: int, state: FeedState | None = None,
           pool_wrapper=None):
    """Run `count` consecutive cycles sharing one state; return their reports."""
    state = state or FeedState()

    async def body(pool):
        target = pool_wrapper(pool) if pool_wrapper else pool
        reports = []
        for _ in range(count):
            try:
                reports.append(await feed_cycle(config(usgs), producer, target, state))
            except OSError as exc:
                reports.append(exc)
        return reports

    return run_with_pool(test_database, body), state


def rows(owner_conn: psycopg.Connection, sql: str) -> list[tuple]:
    return owner_conn.execute(sql).fetchall()


def extractions(owner_conn: psycopg.Connection) -> list[dict]:
    cursor = owner_conn.execute("SELECT * FROM core.extraction ORDER BY extraction_id")
    names = [column.name for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


EARTHQUAKE = feature("E1", time="2026-11-15T08:00:00Z", updated="2026-11-15T08:05:00Z")
BLAST = feature("Q1", time="2026-11-15T08:10:00Z", event_type="quarry blast")
NO_ID = feature(None)


@pytest.fixture
def usgs():
    with FakeUsgs() as stub:
        yield stub


def test_cycle_records_extraction_original_and_exclusions(test_database, owner_conn, usgs) -> None:
    usgs.script(FEED, Reply.json(collection([EARTHQUAKE, BLAST, NO_ID], generated=1794705713000)))
    producer = FakeProducer()

    (report,), _ = cycles(test_database, usgs, producer, 1)

    row = extractions(owner_conn)[0]
    assert (row["source"], row["purpose"], row["outcome"], row["http_status"]) == ("usgs_feed", "live", "ok", 200)
    assert (row["record_count"], row["earthquake_count"], row["excluded_count"], row["published_count"]) == (3, 1, 2, 1)
    assert row["source_generated_at"] == datetime(2026, 11, 15, 1, 21, 53, tzinfo=timezone.utc)
    assert "#2: no id" in row["error_detail"]
    assert report.extraction_id == row["extraction_id"] and report.published == 1

    assert rows(owner_conn, "SELECT event_id, event_type, reason_code, extraction_id FROM core.excluded_event") == [
        ("Q1", "quarry blast", "not_earthquake", row["extraction_id"])
    ]
    (body, sha), = rows(owner_conn, "SELECT body, content_sha256 FROM core.raw_payload")
    assert json.loads(gzip.decompress(body))["features"][0]["id"] == "E1"
    assert sha == row["content_sha256"]
    assert producer.keys("earthquakes.live") == ["E1"]


def test_identical_events_with_new_metadata_keep_one_original(test_database, owner_conn, usgs) -> None:
    usgs.script(FEED, Reply.json(collection([EARTHQUAKE, BLAST], generated=1)),
                Reply.json(collection([EARTHQUAKE, BLAST], generated=2)))
    producer = FakeProducer()

    cycles(test_database, usgs, producer, 2)

    assert len(extractions(owner_conn)) == 2
    (first, last), = rows(owner_conn, "SELECT first_seen_at, last_seen_at FROM core.raw_payload")
    assert last > first
    assert extractions(owner_conn)[1]["published_count"] == 0
    assert rows(owner_conn, "SELECT count(*) FROM core.excluded_event") == [(1,)]
    assert producer.keys() == ["E1"]


def test_not_modified_reuses_the_last_original(test_database, owner_conn, usgs) -> None:
    usgs.script(FEED, Reply.json(collection([EARTHQUAKE]), conditional=True))
    producer = FakeProducer()

    cycles(test_database, usgs, producer, 2)

    first, second = extractions(owner_conn)
    assert (second["outcome"], second["http_status"]) == ("not_modified", 304)
    assert second["content_sha256"] == first["content_sha256"]
    assert (second["record_count"], second["earthquake_count"], second["excluded_count"]) == (None, None, None)
    assert rows(owner_conn, "SELECT count(*) FROM core.raw_payload") == [(1,)]
    requests = usgs.requests_to(FEED)
    assert "If-Modified-Since" not in requests[0].headers and "If-Modified-Since" in requests[1].headers


def test_revision_is_published(test_database, usgs) -> None:
    revised = feature("E1", time="2026-11-15T08:00:00Z", updated="2026-11-15T08:30:00Z", mag=4.8)
    usgs.script(FEED, Reply.json(collection([EARTHQUAKE])), Reply.json(collection([revised])))
    producer = FakeProducer()

    reports, _ = cycles(test_database, usgs, producer, 2)

    assert [report.published for report in reports] == [1, 1]
    assert producer.sent[-1].value["mag"] == 4.8


def test_event_leaving_the_window_is_not_deleted(test_database, owner_conn, usgs) -> None:
    usgs.script(FEED, Reply.json(collection([EARTHQUAKE, BLAST])), Reply.json(collection([])))

    cycles(test_database, usgs, FakeProducer(), 2)

    assert rows(owner_conn, "SELECT event_id FROM core.publish_state") == [("E1",)]
    assert rows(owner_conn, "SELECT event_id FROM core.excluded_event") == [("Q1",)]
    assert extractions(owner_conn)[1]["record_count"] == 0


def test_kafka_failure_keeps_unconfirmed_versions_pending(test_database, owner_conn, usgs) -> None:
    two = [feature("E1", updated="2026-11-15T08:05:00Z"), feature("E2", updated="2026-11-15T08:06:00Z")]
    usgs.script(FEED, Reply.json(collection(two)), Reply.json(collection([]), conditional=True))
    producer = FakeProducer(fail_after=1)
    state = FeedState()

    (failed,), state = cycles(test_database, usgs, producer, 1, state)
    assert failed.published == 1 and failed.publish_error is not None
    assert extractions(owner_conn)[0]["published_count"] == 1
    assert [item.event_id for item in state.pending_publish] == ["E2"]

    producer.fail_after = None
    (retried,), state = cycles(test_database, usgs, producer, 1, state)
    assert retried.published == 1 and retried.publish_error is None
    assert producer.keys() == ["E1", "E2"]
    assert state.pending_publish == []


def test_zero_items_is_a_successful_request(test_database, owner_conn, usgs) -> None:
    usgs.script(FEED, Reply.json(collection([])))

    cycles(test_database, usgs, FakeProducer(), 1)

    row = extractions(owner_conn)[0]
    assert (row["outcome"], row["record_count"], row["earthquake_count"], row["excluded_count"], row["published_count"]) == (
        "ok", 0, 0, 0, 0)


def test_event_changing_type_between_versions(test_database, owner_conn, usgs) -> None:
    as_quake = feature("C1", time="2026-11-15T08:00:00Z", updated="2026-11-15T08:05:00Z")
    as_blast = feature("C1", time="2026-11-15T08:00:00Z", updated="2026-11-15T08:20:00Z", event_type="explosion")
    as_quake_again = feature("C1", time="2026-11-15T08:00:00Z", updated="2026-11-15T08:40:00Z")
    usgs.script(FEED, Reply.json(collection([as_quake])), Reply.json(collection([as_blast])),
                Reply.json(collection([as_quake_again])))
    producer = FakeProducer()

    cycles(test_database, usgs, producer, 3)

    assert len(producer.sent) == 2
    assert [message.value["updated"] for message in producer.sent] == [
        as_quake["properties"]["updated"], as_quake_again["properties"]["updated"]]
    assert rows(owner_conn, "SELECT event_id, event_type FROM core.excluded_event") == [("C1", "explosion")]
    assert rows(owner_conn, "SELECT event_id FROM core.publish_state") == [("C1",)]


def test_database_outage_after_the_response_keeps_the_result(test_database, owner_conn, usgs) -> None:
    usgs.script(FEED, Reply.json(collection([EARTHQUAKE])), Reply.json(collection([feature("E9")])))
    producer = FakeProducer()

    class FlakyPool:
        """First acquire fails as if PostgreSQL were down."""

        def __init__(self, pool) -> None:
            self.pool, self.failures = pool, 1

        def acquire(self):
            if self.failures:
                self.failures -= 1
                raise ConnectionRefusedError("database is down")
            return self.pool.acquire()

    reports, state = cycles(test_database, usgs, producer, 2, pool_wrapper=FlakyPool)

    assert isinstance(reports[0], OSError)
    assert reports[1].published == 1
    assert len(usgs.requests_to(FEED)) == 1            # the source was not asked again
    (row,) = extractions(owner_conn)                    # one extraction, recorded late
    assert row["requested_at"] == reports[1].result.requested_at
    assert row["record_count"] == 1
    assert producer.keys() == ["E1"]
    assert state.unrecorded is None


def test_last_ingestion_ignores_failures(test_database, owner_conn, usgs) -> None:
    usgs.script(FEED, Reply.json(collection([])), Reply.text("busy", status=503))

    reports, _ = cycles(test_database, usgs, FakeProducer(), 2)

    last = owner_conn.execute(
        "SELECT max(requested_at) FROM core.extraction WHERE source = 'usgs_feed' AND outcome IN ('ok','not_modified')"
    ).fetchone()[0]
    assert last == reports[0].result.requested_at
    assert [row["outcome"] for row in extractions(owner_conn)] == ["ok", "http_error"]


@pytest.mark.parametrize(
    ("last_start", "now", "retry_until", "expected"),
    [
        (100.0, 100.0, None, 60.0),     # just started a cycle: wait a full interval
        (100.0, 130.0, None, 30.0),     # the cycle took 30 s
        (100.0, 175.0, None, 0.0),      # the cycle took longer than the interval
        (100.0, 101.0, 400.0, 299.0),   # a long Retry-After pushes the next request
        (100.0, 101.0, 120.0, 59.0),    # a short one never shortens the interval
    ],
)
def test_requests_never_start_closer_than_the_interval(last_start, now, retry_until, expected) -> None:
    assert seconds_until_next_cycle(last_start, now, 60, retry_until) == pytest.approx(expected)
