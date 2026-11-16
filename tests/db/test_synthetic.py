"""Synthetic injection against the real model: idempotent, marked, kept apart from real data."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
import pytest

pytest.importorskip("geopandas")

from tests.synthetic.cases import CASES, PREFIX  # noqa: E402
from tests.synthetic.inject import inject, main  # noqa: E402

from .async_support import run_with_conn  # noqa: E402
from .test_consumer_persistence import FakeMessage, feature_message, handle_all  # noqa: E402

LIVE = "earthquakes.live"
NOW = datetime.now(timezone.utc).replace(microsecond=0)


class RecordingProducer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, bytes, bytes]] = []

    async def send_and_wait(self, topic: str, value: bytes | None = None, key: bytes | None = None, **_: Any) -> None:
        assert value is not None and key is not None
        self.sent.append((topic, value, key))


def do_inject(test_database: str, producer: RecordingProducer, batch: int = 0) -> tuple[int, int]:
    return run_with_conn(test_database, lambda conn: inject(producer, conn, LIVE, batch=batch, out=lambda _: None))


def consume(test_database: str, producer: RecordingProducer, start: int = 0) -> None:
    messages = [FakeMessage(LIVE, start + i, value) for i, (_, value, _) in enumerate(producer.sent)]
    handle_all(test_database, messages)
    producer.sent.clear()


def totals(conn: psycopg.Connection) -> tuple:
    return conn.execute(
        """SELECT (SELECT count(*) FROM core.quarantine), (SELECT count(*) FROM core.event_current),
                  (SELECT count(*) FROM core.event_version), (SELECT count(*) FROM core.excluded_event),
                  (SELECT count(*) FROM core.message_log)"""
    ).fetchone()


def test_injecting_twice_adds_nothing(test_database: str, owner_conn: psycopg.Connection) -> None:
    producer = RecordingProducer()
    published, skipped = do_inject(test_database, producer, batch=5)
    assert (published, skipped) == (len(CASES) + 5, 0)
    assert len(producer.sent) == published
    consume(test_database, producer)
    before = totals(owner_conn)

    published, skipped = do_inject(test_database, producer, batch=5)
    assert (published, skipped) == (0, len(CASES) + 5)
    assert producer.sent == []
    assert totals(owner_conn) == before


def test_everything_generated_is_marked_and_apart_from_real_data(test_database: str, owner_conn: psycopg.Connection) -> None:
    real = feature_message("us-real-1", NOW - timedelta(hours=1), NOW - timedelta(minutes=50))
    handle_all(test_database, [FakeMessage(LIVE, 0, real)])
    producer = RecordingProducer()
    do_inject(test_database, producer, batch=3)
    consume(test_database, producer, start=10)

    events = owner_conn.execute("SELECT event_id, quality_flags FROM core.event_current").fetchall()
    assert any(event_id == "us-real-1" and "synthetic" not in flags for event_id, flags in events)
    for event_id, flags in events:
        assert event_id.startswith(PREFIX) == ("synthetic" in flags)
    assert owner_conn.execute(
        "SELECT count(*) FROM core.event_version WHERE event_id LIKE 'synthetic-%'"
    ).fetchone()[0] == sum(1 for e, _ in events if e.startswith(PREFIX))

    rows = owner_conn.execute("SELECT is_synthetic, payload::text, raw_text FROM core.quarantine").fetchall()
    assert rows
    for is_synthetic, payload, raw in rows:
        assert is_synthetic or PREFIX in (payload or raw)
    assert owner_conn.execute("SELECT count(*) FROM core.quarantine WHERE NOT is_synthetic").fetchone()[0] <= 2
    assert owner_conn.execute("SELECT event_id FROM core.excluded_event ORDER BY 1").fetchall() == [
        ("synthetic-missing_type",), ("synthetic-not_earthquake",)]

    quarantined = {code for (codes,) in owner_conn.execute("SELECT reason_codes FROM core.quarantine").fetchall() for code in codes}
    expected = {code for c in CASES if c.outcome == "quarantine" for code in c.codes}
    assert quarantined == expected

    assert owner_conn.execute("SELECT magnitude IS NULL FROM core.event_current WHERE event_id = 'synthetic-null_magnitude'").fetchone() == (True,)
    # Real data stays free of marks.
    assert owner_conn.execute("SELECT count(*) FROM core.event_current WHERE event_id NOT LIKE 'synthetic-%' AND 'synthetic' = ANY (quality_flags)").fetchone()[0] == 0


def test_list_prints_every_case(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--list"])
    output = capsys.readouterr().out
    assert all(case.case in output for case in CASES)
