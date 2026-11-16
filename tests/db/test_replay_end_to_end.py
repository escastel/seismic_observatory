"""A replay end to end: selection, publication and the real consumer handler (spec 005, T013).

Kafka is simulated by handing every published message to the consumer's MessageHandler with the
replay topic, so the replay path (selection -> run_replay -> consumer -> replay schema) is the real
one and core is compared before and after.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

pytest.importorskip("geopandas")

from common.settings import TopicNames  # noqa: E402
from consumer.app.main import MessageHandler  # noqa: E402
from producer.app.replay import isolation  # noqa: E402
from producer.app.replay.runner import ReplayItem, run_replay  # noqa: E402
from producer.app.replay.selection import locate_files, register_selection, select_events, set_published_count  # noqa: E402
from producer.app.catalog import Interval  # noqa: E402
from tests.db.async_support import writer_pool  # noqa: E402
from tests.db.test_consumer_persistence import FakeMessage, FixedCountry  # noqa: E402
from tests.db.test_consumer_rules import flat  # noqa: E402
from tests.db.test_replay_selection import load_month  # noqa: E402
from tests.support.usgs_stub import feature  # noqa: E402

JAN = datetime(2025, 1, 1, tzinfo=timezone.utc)
FEB = datetime(2025, 2, 1, tzinfo=timezone.utc)
EVENTS = 240
REPLAY, LIVE = "earthquakes.replay", "earthquakes.live"


def january(n: int = EVENTS) -> list:
    return [
        feature(f"hist-{i:04d}", JAN + timedelta(minutes=10 * i), mag=4.0 + (i % 30) / 10, longitude=-3.7, latitude=40.4)
        for i in range(n)
    ]


class DeliveringProducer:
    """Kafka stand-in: each confirmed message goes straight to the consumer handler."""

    def __init__(self, handler: MessageHandler) -> None:
        self.handler = handler
        self.outcomes: list[str] = []

    async def send_and_wait(self, topic: str, value: bytes | None = None, key: bytes | None = None, **_) -> None:
        assert topic == REPLAY and key is not None and value is not None
        self.outcomes.append(await self.handler(FakeMessage(topic, len(self.outcomes), value)))


class FakeClock:
    now = 0.0

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds


def replay_once(test_database: str, tmp_path, features: list, *, core_event: dict | None = None) -> dict:
    """Load the catalog, optionally seed core, then select, publish and consume; returns the facts."""

    async def run() -> dict:
        core_pool = await writer_pool(test_database, "core")
        replay_pool = await writer_pool(test_database, "replay, core")
        try:
            async with core_pool.acquire() as conn:
                await load_month(conn, tmp_path, Interval(JAN, FEB), features)
            handler = MessageHandler({"core": core_pool, "replay, core": replay_pool}, TopicNames(), FixedCountry("ESP"))
            if core_event is not None:
                assert await handler(FakeMessage(LIVE, 0, json.dumps(core_event).encode())) == "new"
            async with core_pool.acquire() as conn:
                before = await isolation.take_snapshot(conn)
                files = await locate_files(conn, tmp_path, JAN, FEB, 4.0)
                selection = select_events(files, JAN, FEB, 4.0)
                extraction_id = await register_selection(conn, selection)
            producer = DeliveringProducer(handler)
            clock = FakeClock()
            sent = await run_replay(
                producer, [ReplayItem(f) for f in selection.features], topic=REPLAY, extraction_id=extraction_id,
                rate=1000.0, speedup=None, control_dir=tmp_path / "control", clock=clock, sleep=clock.sleep, run_id="e2e",
            )
            async with core_pool.acquire() as conn:
                await set_published_count(conn, extraction_id, sent)
                after = await isolation.take_snapshot(conn)
            return {"selection": selection, "sent": sent, "outcomes": producer.outcomes, "diff": isolation.compare(before, after),
                    "extraction_id": extraction_id}
        finally:
            await core_pool.close()
            await replay_pool.close()

    return asyncio.run(run())


def test_replay_lands_only_in_the_replay_schema_and_core_is_untouched(test_database, owner_conn, tmp_path) -> None:
    features = january()
    result = replay_once(test_database, tmp_path, features)

    assert result["sent"] == result["selection"].count == EVENTS
    assert result["outcomes"] == ["new"] * EVENTS
    assert result["diff"] == []  # every core table has the same count and checksum
    assert owner_conn.execute("SELECT count(*) FROM replay.event_current").fetchone()[0] == EVENTS
    assert owner_conn.execute("SELECT count(*) FROM core.event_current").fetchone()[0] == 0
    assert owner_conn.execute("SELECT published_count FROM core.extraction WHERE extraction_id = %s",
                              (result["extraction_id"],)).fetchone()[0] == EVENTS


def test_original_times_are_kept_and_replayed_at_is_added(test_database, owner_conn, tmp_path) -> None:
    features = january()
    replay_once(test_database, tmp_path, features)

    stored = owner_conn.execute(
        "SELECT event_id, (extract(epoch FROM event_time) * 1000)::bigint, (extract(epoch FROM updated_at) * 1000)::bigint, "
        "replayed_at FROM replay.event_current ORDER BY event_id").fetchall()
    expected = sorted((f["id"], f["properties"]["time"], f["properties"]["updated"]) for f in features)
    assert [(r[0], r[1], r[2]) for r in stored] == expected
    now = datetime.now(timezone.utc)
    assert all(r[3] is not None and now - timedelta(minutes=5) <= r[3] <= now for r in stored)  # not shifted to look recent
    assert owner_conn.execute("SELECT count(*) FROM replay.event_version WHERE kafka_topic <> %s", (REPLAY,)).fetchone()[0] == 0


def test_same_event_id_in_core_and_replay_keeps_each_value(test_database, owner_conn: psycopg.Connection, tmp_path) -> None:
    live = flat("hist-0000", mag=2.0)
    result = replay_once(test_database, tmp_path, january(), core_event=live)

    assert result["diff"] == []
    core_mag = owner_conn.execute("SELECT magnitude FROM core.event_current WHERE event_id = 'hist-0000'").fetchone()[0]
    replay_mag = owner_conn.execute("SELECT magnitude FROM replay.event_current WHERE event_id = 'hist-0000'").fetchone()[0]
    assert (core_mag, replay_mag) == (2.0, 4.0)
