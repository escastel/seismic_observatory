"""The five synthetic replay cases end up where the contract says (spec 005, T021).

Expected results: specs/005-historical-replay/contracts/synthetic-cases.md. The seven messages go
through the real replay runner and the real consumer handler; the checks are the contract queries.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import psycopg
import pytest

pytest.importorskip("geopandas")

from common.settings import TopicNames  # noqa: E402
from consumer.app.main import MessageHandler  # noqa: E402
from producer.app.replay.runner import run_replay  # noqa: E402
from producer.app.replay.synthetic import synthetic_items  # noqa: E402
from tests.db.async_support import writer_pool  # noqa: E402
from tests.db.test_consumer_persistence import FixedCountry  # noqa: E402
from tests.db.test_replay_end_to_end import REPLAY, DeliveringProducer, FakeClock  # noqa: E402

U1 = datetime(2025, 6, 15, 12, 10, tzinfo=timezone.utc)
U2 = datetime(2025, 6, 15, 13, 30, tzinfo=timezone.utc)
LIKE = "synthetic-replay-%"


def replay_synthetic(test_database: str, tmp_path) -> list[str]:
    async def run() -> list[str]:
        core_pool = await writer_pool(test_database, "core")
        replay_pool = await writer_pool(test_database, "replay, core")
        try:
            handler = MessageHandler({"core": core_pool, "replay, core": replay_pool}, TopicNames(), FixedCountry("ESP"))
            producer, clock = DeliveringProducer(handler), FakeClock()
            sent = await run_replay(
                producer, synthetic_items(), topic=REPLAY, extraction_id=None, rate=1000.0, speedup=None,
                control_dir=tmp_path, clock=clock, sleep=clock.sleep, run_id="synthetic",
            )
            assert sent == 7
            return producer.outcomes
        finally:
            await core_pool.close()
            await replay_pool.close()

    return asyncio.run(run())


def test_each_message_gets_its_expected_outcome(test_database, owner_conn: psycopg.Connection, tmp_path) -> None:
    outcomes = replay_synthetic(test_database, tmp_path)

    assert outcomes == ["new", "duplicate", "new", "revised", "new", "stale", "quarantined"]
    counts = dict(owner_conn.execute(
        "SELECT outcome, count(*) FROM replay.message_log WHERE event_id LIKE %s OR outcome = 'quarantined' "
        "GROUP BY outcome", (LIKE,)).fetchall())
    assert counts == {"new": 3, "duplicate": 1, "revised": 1, "stale": 1, "quarantined": 1}


def test_current_state_takes_the_revision_and_never_goes_back(test_database, owner_conn, tmp_path) -> None:
    replay_synthetic(test_database, tmp_path)

    current = {row[0]: row[1:] for row in owner_conn.execute(
        "SELECT event_id, magnitude, updated_at, quality_flags FROM replay.event_current WHERE event_id LIKE %s", (LIKE,))}
    assert set(current) == {"synthetic-replay-first", "synthetic-replay-revised", "synthetic-replay-stale"}
    assert current["synthetic-replay-first"][0] == 4.1
    assert current["synthetic-replay-revised"][:2] == (4.4, U2)
    assert current["synthetic-replay-stale"][1] == U2  # the late old version did not move it back
    assert all("synthetic" in flags[2] for flags in current.values())
    versions = dict(owner_conn.execute(
        "SELECT event_id, count(*) FROM replay.event_version WHERE event_id LIKE %s GROUP BY event_id", (LIKE,)).fetchall())
    assert versions == {"synthetic-replay-first": 1, "synthetic-replay-revised": 2, "synthetic-replay-stale": 2}


def test_bad_coordinates_go_to_quarantine_with_their_reason(test_database, owner_conn, tmp_path) -> None:
    replay_synthetic(test_database, tmp_path)

    rows = owner_conn.execute("SELECT event_id, reason_codes, is_synthetic, payload IS NOT NULL FROM replay.quarantine").fetchall()
    assert len(rows) == 1
    event_id, reasons, is_synthetic, has_original = rows[0]
    assert event_id == "synthetic-replay-bad-coordinates"
    assert "coordinates_out_of_range" in reasons and is_synthetic and has_original


def test_nothing_synthetic_reaches_core(test_database, owner_conn, tmp_path) -> None:
    replay_synthetic(test_database, tmp_path)

    for table in ("event_current", "event_version", "quarantine", "excluded_event", "message_log"):
        column = "event_id"
        assert owner_conn.execute(f"SELECT count(*) FROM core.{table} WHERE {column} LIKE %s", (LIKE,)).fetchone()[0] == 0  # noqa: S608
