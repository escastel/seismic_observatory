"""Source failures during the live feed (US3: FR-015 to FR-017, FR-006, SC-008, SC-009)."""

from __future__ import annotations

import gzip

import psycopg
import pytest

from producer.app.main import FeedState, feed_cycle
from tests.db.async_support import run_with_pool
from tests.db.test_feed_cycle import config
from tests.support.fake_kafka import FakeProducer
from tests.support.usgs_stub import FakeUsgs, Reply, collection, feature

FEED = "/feed"
GOOD = Reply.json(collection([feature("E1", time="2026-11-15T08:00:00Z", updated="2026-11-15T08:05:00Z")]))
REVISED = Reply.json(collection([feature("E1", time="2026-11-15T08:00:00Z", updated="2026-11-15T08:30:00Z", mag=5.0)]))


def run_cycles(test_database, usgs, producer, state, count, attempts=1, timeout=2):
    settings = config(usgs)
    settings = settings.__class__(**{**settings.__dict__, "usgs": settings.usgs.__class__(
        **{**settings.usgs.__dict__, "max_attempts": attempts, "timeout_seconds": timeout})})

    async def body(pool):
        return [await feed_cycle(settings, producer, pool, state) for _ in range(count)]

    return run_with_pool(test_database, body)


def snapshot(owner_conn: psycopg.Connection) -> dict:
    def one(sql):
        return owner_conn.execute(sql).fetchall()

    return {
        "publish_state": one("SELECT event_id, updated_at FROM core.publish_state ORDER BY 1"),
        "excluded": one("SELECT event_id, updated_at FROM core.excluded_event ORDER BY 1"),
        "last_ingestion": one("SELECT max(requested_at) FROM core.extraction "
                              "WHERE source = 'usgs_feed' AND outcome IN ('ok', 'not_modified')"),
    }


def last_extraction(owner_conn) -> dict:
    cursor = owner_conn.execute("SELECT * FROM core.extraction ORDER BY extraction_id DESC LIMIT 1")
    names = [column.name for column in cursor.description]
    return dict(zip(names, cursor.fetchone()))


FAILURES = [
    ("rate-limited", Reply.text("Too Many Requests", status=429, headers={"Retry-After": "1"}), "http_error", 429),
    ("server-error", Reply.text("Service Unavailable", status=503), "http_error", 503),
    ("timeout", Reply(delay=3), "timeout", None),
    ("not-json", Reply.text("<html>maintenance</html>"), "invalid_json", 200),
    ("bad-structure", Reply.json({"type": "FeatureCollection", "features": "none"}), "invalid_structure", 200),
]


@pytest.mark.parametrize(("name", "failure", "outcome", "status"), FAILURES, ids=[f[0] for f in FAILURES])
def test_failure_is_recorded_and_changes_nothing_else(test_database, owner_conn, name, failure, outcome, status) -> None:
    producer = FakeProducer()
    state = FeedState()
    retried = outcome in ("http_error", "timeout")      # these use both attempts of the cycle
    with FakeUsgs() as usgs:
        usgs.script(FEED, GOOD, *([failure] * (2 if retried else 1)), REVISED)
        run_cycles(test_database, usgs, producer, state, 1)           # a good cycle first
        before = snapshot(owner_conn)

        reports = run_cycles(test_database, usgs, producer, state, 1, attempts=2, timeout=1)

        row = last_extraction(owner_conn)
        assert (row["outcome"], row["http_status"], row["attempt_count"]) == (outcome, status, 2 if retried else 1)
        assert row["error_detail"]
        assert (row["record_count"], row["earthquake_count"], row["excluded_count"], row["published_count"]) == (None,) * 4
        assert reports[0].published == 0 and len(producer.sent) == 1
        assert snapshot(owner_conn) == before                          # nothing published, marked or deleted

        if outcome in ("invalid_json", "invalid_structure"):          # the answer is kept for diagnosis
            (body,) = owner_conn.execute("SELECT body FROM core.raw_payload WHERE content_sha256 = %s",
                                         (row["content_sha256"],)).fetchone()
            assert gzip.decompress(body).startswith(b"<html>" if outcome == "invalid_json" else b'{"type"')
        else:
            assert row["content_sha256"] is None

        (recovered,) = run_cycles(test_database, usgs, producer, state, 1)
        assert recovered.result.outcome == "ok" and recovered.published == 1
    assert producer.sent[-1].value["mag"] == 5.0


def test_transient_error_then_success_is_one_extraction(test_database, owner_conn) -> None:
    with FakeUsgs() as usgs:
        usgs.script(FEED, Reply.text("busy", status=503), GOOD)
        run_cycles(test_database, usgs, FakeProducer(), FeedState(), 1, attempts=4)

    (row,) = owner_conn.execute("SELECT outcome, attempt_count, http_status FROM core.extraction").fetchall()
    assert row == ("ok", 2, 200)


def test_long_retry_after_postpones_the_next_request(test_database, owner_conn, monkeypatch) -> None:
    clock = [1_000.0]
    monkeypatch.setattr("producer.app.main.time.monotonic", lambda: clock[0])
    state = FeedState()
    with FakeUsgs() as usgs:
        usgs.script(FEED, Reply.text("later", status=429, headers={"Retry-After": "300"}))
        (report,) = run_cycles(test_database, usgs, FakeProducer(), state, 1, attempts=4)

    assert report.result.attempt_count == 1          # not retried inside the cycle
    assert state.retry_after_until == 1_300.0

    from producer.app.main import seconds_until_next_cycle

    assert seconds_until_next_cycle(1_000.0, 1_001.0, 60, state.retry_after_until) == pytest.approx(299.0)
