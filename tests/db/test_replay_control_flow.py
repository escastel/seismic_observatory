"""Pause, resume, stop and repeat after reset against the real database (spec 005, T017).

The runner and the consumer handler are the real ones; Kafka is simulated. Control orders are
written at known moments through the injected delivery and sleep hooks, so the test is deterministic.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

pytest.importorskip("geopandas")

from common.settings import TopicNames  # noqa: E402
from consumer.app.main import MessageHandler  # noqa: E402
from producer.app.catalog import Interval  # noqa: E402
from producer.app.replay import control, isolation  # noqa: E402
from producer.app.replay.runner import ReplayItem, run_replay  # noqa: E402
from producer.app.replay.selection import locate_files, register_selection, select_events  # noqa: E402
from tests.db.async_support import writer_pool  # noqa: E402
from tests.db.test_consumer_persistence import FakeMessage, FixedCountry  # noqa: E402
from tests.db.test_replay_selection import load_month  # noqa: E402
from tests.support.usgs_stub import feature  # noqa: E402

JAN = datetime(2025, 1, 1, tzinfo=timezone.utc)
FEB = datetime(2025, 2, 1, tzinfo=timezone.utc)
TOTAL = 120
REPLAY = "earthquakes.replay"
STATE_SQL = ("SELECT count(*), coalesce(sum(hashtextextended(event_id || event_time::text || updated_at::text "
             "|| coalesce(magnitude::text, ''), 0)::numeric), 0) FROM replay.event_current")


def january() -> list:
    return [feature(f"hist-{i:04d}", JAN + timedelta(minutes=10 * i), mag=4.0 + (i % 30) / 10) for i in range(TOTAL)]


class Flow:
    """One replay run with hooks: on_delivery(k, flow) after the k-th delivery, on_sleep(n, flow) at each sleep."""

    def __init__(self, test_database: str, tmp_path, on_delivery: Callable | None = None, on_sleep: Callable | None = None):
        self.test_database, self.dir = test_database, tmp_path
        self.on_delivery, self.on_sleep = on_delivery, on_sleep
        self.outcomes: list[str] = []
        self.ids: list[str] = []
        self.sleeps = 0
        self.now = 0.0
        self.sent_when_paused: list[int] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps += 1
        self.now += seconds
        if self.on_sleep:
            self.on_sleep(self.sleeps, self)

    async def send_and_wait(self, topic, value=None, key=None, **_) -> None:
        self.outcomes.append(await self.handler(FakeMessage(topic, len(self.outcomes), value)))
        self.ids.append(key.decode())
        if self.on_delivery:
            self.on_delivery(len(self.outcomes), self)

    def run(self, features: list) -> dict:
        async def go() -> dict:
            core, replay = await writer_pool(self.test_database, "core"), await writer_pool(self.test_database, "replay, core")
            try:
                self.handler = MessageHandler({"core": core, "replay, core": replay}, TopicNames(), FixedCountry("ESP"))
                async with core.acquire() as conn:
                    if not await conn.fetchval("SELECT count(*) FROM core.extraction WHERE purpose = 'historical_load'"):
                        await load_month(conn, self.dir, Interval(JAN, FEB), features)
                    before = await isolation.take_snapshot(conn)
                    files = await locate_files(conn, self.dir, JAN, FEB, 4.0)
                    selection = select_events(files, JAN, FEB, 4.0)
                    extraction_id = await register_selection(conn, selection)
                sent = await run_replay(self, [ReplayItem(f) for f in selection.features], topic=REPLAY, extraction_id=extraction_id,
                                        rate=1000.0, speedup=None, control_dir=self.dir / "control", clock=self, sleep=self.sleep,
                                        run_id="flow")
                async with core.acquire() as conn:
                    after = await isolation.take_snapshot(conn)
                return {"sent": sent, "diff": isolation.compare(before, after), "order": [f["id"] for f in selection.features]}
            finally:
                await core.close()
                await replay.close()

        return asyncio.run(go())


def state(conn: psycopg.Connection) -> tuple:
    return conn.execute(STATE_SQL).fetchone()


def test_pause_stops_publication_and_resume_continues_without_gaps(test_database, owner_conn, tmp_path) -> None:
    def pause_at_40(count: int, flow: Flow) -> None:
        if count == 40:
            control.write_control(flow.dir / "control", "pause")

    def resume_after_a_while(n: int, flow: Flow) -> None:
        if control.read_status(flow.dir / "control")["state"] == "paused":
            flow.sent_when_paused.append(len(flow.outcomes))
            if len(flow.sent_when_paused) == 10:
                control.write_control(flow.dir / "control", "resume")

    flow = Flow(test_database, tmp_path, pause_at_40, resume_after_a_while)
    result = flow.run(january())

    assert result["sent"] == TOTAL and result["diff"] == []
    assert set(flow.sent_when_paused) == {40}  # nothing was published while paused
    assert flow.ids == result["order"]  # no event skipped or repeated, same order
    assert flow.outcomes == ["new"] * TOTAL
    assert state(owner_conn)[0] == TOTAL
    assert control.read_status(tmp_path / "control")["state"] == "finished"


def test_stop_keeps_what_was_published_and_reset_plus_repeat_gives_the_same_result(test_database, owner_conn, tmp_path) -> None:
    def stop_at_50(count: int, flow: Flow) -> None:
        if count == 50:
            control.write_control(flow.dir / "control", "stop")

    stopped = Flow(test_database, tmp_path, stop_at_50)
    first = stopped.run(january())
    assert first["sent"] == 50 and first["diff"] == []
    assert control.read_status(tmp_path / "control")["state"] == "stopped"
    assert state(owner_conn)[0] == 50  # lo ya publicado se conserva

    owner_conn.execute("SELECT replay.reset()")
    assert state(owner_conn)[0] == 0

    complete = Flow(test_database, tmp_path)
    second = complete.run(january())
    assert second["sent"] == TOTAL and second["diff"] == []
    result_first_run = state(owner_conn)

    owner_conn.execute("SELECT replay.reset()")
    third = Flow(test_database, tmp_path).run(january())
    assert third["diff"] == [] and state(owner_conn) == result_first_run  # repeating gives the identical result
