"""A consumer restart in the middle of a replay changes nothing in the end (spec 005, T022).

At-least-once delivery means a restarted consumer may read again some messages it had already
written. The final state must equal a run without restart, replayed_at included (research R1).
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
from producer.app.replay.message import build_replay_message, encode  # noqa: E402
from tests.db.async_support import writer_pool  # noqa: E402
from tests.db.test_consumer_persistence import FakeMessage, FixedCountry  # noqa: E402
from tests.support.usgs_stub import feature  # noqa: E402

JAN = datetime(2025, 1, 1, tzinfo=timezone.utc)
STAMP = datetime(2026, 11, 16, 10, 0, tzinfo=timezone.utc)
REPLAY = "earthquakes.replay"
TOTAL = 200


def messages() -> list[bytes]:
    features = [feature(f"hist-{i:04d}", JAN + timedelta(minutes=10 * i), mag=4.0 + (i % 30) / 10) for i in range(TOTAL)]
    return [encode(build_replay_message(f, extraction_id=None, replayed_at=STAMP + timedelta(seconds=n), run="restart"))
            for n, f in enumerate(features)]


def consume(test_database: str, batches: list[range], payloads: list[bytes]) -> list[str]:
    """Each batch is read by a brand new handler (a restarted consumer); offsets are the message numbers."""

    async def run() -> list[str]:
        core, replay = await writer_pool(test_database, "core"), await writer_pool(test_database, "replay, core")
        outcomes: list[str] = []
        try:
            for batch in batches:
                handler = MessageHandler({"core": core, "replay, core": replay}, TopicNames(), FixedCountry("ESP"))
                for offset in batch:
                    outcomes.append(await handler(FakeMessage(REPLAY, offset, payloads[offset])))
            return outcomes
        finally:
            await core.close()
            await replay.close()

    return asyncio.run(run())


def final_state(conn: psycopg.Connection) -> tuple:
    current = conn.execute(
        "SELECT count(*), coalesce(sum(hashtextextended(event_id || event_time::text || updated_at::text || "
        "replayed_at::text || coalesce(magnitude::text, ''), 0)::numeric), 0) FROM replay.event_current").fetchone()
    versions = conn.execute("SELECT count(*) FROM replay.event_version").fetchone()[0]
    quarantined = conn.execute("SELECT count(*) FROM replay.quarantine").fetchone()[0]
    return current, versions, quarantined


def test_restart_in_the_middle_gives_the_same_final_state(test_database, owner_conn: psycopg.Connection) -> None:
    payloads = messages()
    consume(test_database, [range(TOTAL)], payloads)
    expected = final_state(owner_conn)
    assert expected[0][0] == TOTAL and expected[1] == TOTAL and expected[2] == 0

    owner_conn.execute("SELECT replay.reset()")
    # The first consumer stops after 100 messages; the second restarts from offset 80 (offsets 80-99 are read twice).
    outcomes = consume(test_database, [range(0, 100), range(80, TOTAL)], payloads)

    assert final_state(owner_conn) == expected
    assert outcomes[100:120] == ["duplicate"] * 20  # re-reading changes nothing
    assert outcomes.count("new") == TOTAL


def test_a_message_read_twice_keeps_the_replayed_at_it_carries(test_database, owner_conn) -> None:
    payloads = messages()
    consume(test_database, [range(0, 10), range(0, 10)], payloads)

    rows = owner_conn.execute("SELECT event_id, replayed_at FROM replay.event_current ORDER BY event_id").fetchall()
    assert len(rows) == 10
    carried = [datetime.fromisoformat(json.loads(payloads[n])["replayed_at"].replace("Z", "+00:00")) for n in range(10)]
    assert [r[1] for r in rows] == carried == [STAMP + timedelta(seconds=n) for n in range(10)]
