"""replayed_at of a replay message reaches replay.event_current (spec 005, research R1)."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

pytest.importorskip("geopandas")

from common.settings import TopicNames  # noqa: E402
from consumer.app.main import MessageHandler  # noqa: E402
from tests.db.async_support import writer_pool  # noqa: E402
from tests.db.test_consumer_persistence import FakeMessage, FixedCountry  # noqa: E402
from tests.db.test_consumer_rules import flat  # noqa: E402

REPLAY, LIVE = "earthquakes.replay", "earthquakes.live"
STAMP = "2026-11-16T10:00:00+00:00"


def deliver(test_database: str, topic: str, message: dict) -> str:
    async def run() -> str:
        core = await writer_pool(test_database, "core")
        replay = await writer_pool(test_database, "replay, core")
        try:
            handler = MessageHandler({"core": core, "replay, core": replay}, TopicNames(), FixedCountry("ESP"))
            return await handler(FakeMessage(topic, 0, json.dumps(message).encode()))
        finally:
            await core.close()
            await replay.close()

    return asyncio.run(run())


def replayed_at(conn: psycopg.Connection, schema: str, event_id: str = "E1") -> datetime | None:
    return conn.execute(f"SELECT replayed_at FROM {schema}.event_current WHERE event_id = %s", (event_id,)).fetchone()[0]


def test_replay_message_keeps_the_replayed_at_it_carries(test_database: str, owner_conn: psycopg.Connection) -> None:
    assert deliver(test_database, REPLAY, flat(replayed_at=STAMP, mode="replay")) == "new"

    assert replayed_at(owner_conn, "replay") == datetime(2026, 11, 16, 10, 0, tzinfo=timezone.utc)
    assert owner_conn.execute("SELECT count(*) FROM core.event_current").fetchone()[0] == 0


def test_message_without_replayed_at_gets_the_reading_time(test_database: str, owner_conn: psycopg.Connection) -> None:
    before = datetime.now(timezone.utc)
    deliver(test_database, REPLAY, flat())

    stamped = replayed_at(owner_conn, "replay")
    assert before - timedelta(seconds=5) <= stamped <= datetime.now(timezone.utc) + timedelta(seconds=5)


def test_unreadable_replayed_at_is_not_a_quarantine_reason(test_database: str, owner_conn: psycopg.Connection) -> None:
    assert deliver(test_database, REPLAY, flat(replayed_at="not a date")) == "new"

    assert replayed_at(owner_conn, "replay") is not None
    assert owner_conn.execute("SELECT count(*) FROM replay.quarantine").fetchone()[0] == 0


def test_real_topic_ignores_replayed_at(test_database: str, owner_conn: psycopg.Connection) -> None:
    assert deliver(test_database, LIVE, flat(replayed_at=STAMP)) == "new"

    assert replayed_at(owner_conn, "core") is None
    assert owner_conn.execute("SELECT count(*) FROM replay.event_current").fetchone()[0] == 0
