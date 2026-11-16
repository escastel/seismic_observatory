"""Historical replay runner (specs/005-historical-replay, research R6, data-model sections 4-5).

Publishes the selected events in order, awaiting Kafka's confirmation of each
one (principle II). If a send fails the run ends in state `failed` and nothing
else is published. Pause/stop (T015) and the advisory lock (T016) are handled here.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from . import control, message, pacing

STATUS_PERIOD_SECONDS = 1.0
POLL_SECONDS = 0.25  # control polling period: a pause takes effect well under 2 s


class KafkaProducer(Protocol):
    async def send_and_wait(self, topic: str, value: bytes | None = None, key: bytes | None = None, **kwargs: Any) -> Any: ...


LOCK_KEY = 5005001  # constant advisory-lock key: one replay at a time (research R4)


class RunLockBusy(RuntimeError):
    """Another replay (or a reset) holds the advisory lock."""


class ReplayLock(Protocol):
    """Advisory lock guarding one replay at a time."""

    async def acquire(self) -> bool: ...

    async def release(self) -> None: ...


class ActiveRunLock:
    """`pg_try_advisory_lock` on a dedicated connection kept open while held.

    The lock belongs to the session, so PostgreSQL frees it if the process dies.
    `acquire` is idempotent while held, so the CLI can take it before registering
    the selection and the runner can take it again without conflict.
    """

    def __init__(self, dsn: str, key: int = LOCK_KEY) -> None:
        self.dsn = dsn
        self.key = key
        self._conn: Any = None

    @property
    def held(self) -> bool:
        return self._conn is not None

    async def acquire(self) -> bool:
        if self._conn is not None:
            return True
        import asyncpg

        conn = await asyncpg.connect(self.dsn, server_settings={"application_name": "replay-lock"})
        try:
            got = await conn.fetchval("SELECT pg_try_advisory_lock($1)", self.key)
        except BaseException:
            await conn.close()
            raise
        if not got:
            await conn.close()
            return False
        self._conn = conn
        return True

    async def release(self) -> None:
        conn, self._conn = self._conn, None
        if conn is None:
            return
        try:
            await conn.execute("SELECT pg_advisory_unlock($1)", self.key)
        except Exception:
            pass  # closing the session frees the lock anyway
        finally:
            await conn.close()


@dataclass(frozen=True)
class ReplayItem:
    feature: dict[str, Any]
    synthetic_case: str | None = None

    @property
    def event_id(self) -> str:
        return self.feature["id"]

    @property
    def time_ms(self) -> float:
        return self.feature["properties"]["time"]


class _Run:
    def __init__(
        self,
        producer: KafkaProducer,
        items: Sequence[ReplayItem],
        *,
        topic: str,
        extraction_id: int | None,
        rate: float | None,
        speedup: float | None,
        control_dir: str | Path,
        lock: ReplayLock | None,
        clock: Callable[[], float],
        sleep: Callable[[float], Awaitable[None]],
        run_id: str,
        now: Callable[[], datetime],
    ) -> None:
        self.producer = producer
        self.items = items
        self.topic = topic
        self.extraction_id = extraction_id
        self.rate = rate
        self.speedup = speedup
        self.control_dir = control_dir
        self.lock = lock
        self.clock = clock
        self.sleep = sleep
        self.run_id = run_id
        self.now = now
        self.sent = 0
        self.schedule = pacing.Schedule(clock)
        self._last_status = clock()
        self._started_at = now().isoformat()
        self._paused = False

    def _status(self, state: str, error: str | None = None) -> None:
        control.write_status(
            self.control_dir,
            run=self.run_id,
            state=state,
            total=len(self.items),
            sent=self.sent,
            remaining=len(self.items) - self.sent,
            rate_target=self.rate,
            speedup=self.speedup,
            started_at=self._started_at,
            extraction_id=self.extraction_id,
            error=error,
        )
        self._last_status = self.clock()

    async def _checkpoint(self) -> bool:
        """Consume a pending order. Returns False when the run was stopped.

        `pause` blocks here (polling) until `resume` or `stop`; the Schedule is
        rebased on resume so the replay does not catch up in a burst.
        """
        order = control.consume_control(self.control_dir)
        command = order.get("command") if order else None
        if command == "stop":
            self._status("stopped")
            return False
        if command != "pause":
            return True
        self._status("paused")
        while True:
            await self.sleep(POLL_SECONDS)
            order = control.consume_control(self.control_dir)
            command = order.get("command") if order else None
            if command == "stop":
                self._status("stopped")
                return False
            if command == "resume":
                break
        self.schedule = pacing.Schedule(self.clock)  # rebase after a pause
        self.schedule.delay(0.0)
        self._paused = True
        self._status("running")
        return True

    async def _wait(self, step: float) -> bool:
        """Wait for the schedule in slices of at most POLL_SECONDS, polling control."""
        remaining = self.schedule.delay(step)
        deadline = self.clock() + remaining
        while True:
            self._paused = False
            if not await self._checkpoint():
                return False
            if self._paused or remaining <= 0:  # after a pause the schedule is rebased: send now
                return True
            await self.sleep(min(remaining, POLL_SECONDS))
            remaining = deadline - self.clock()

    async def execute(self) -> int:
        if self.lock is not None:
            if not await self.lock.acquire():
                raise RunLockBusy("ya hay una reproducción activa")
            try:
                return await self._execute()
            finally:
                await self.lock.release()
        return await self._execute()

    async def _execute(self) -> int:
        control.consume_control(self.control_dir)  # discard any stale order
        self._status("running")
        previous: ReplayItem | None = None
        for item in self.items:
            if not await self._checkpoint():
                return self.sent
            if previous is not None:
                step = pacing.interval(previous.time_ms, item.time_ms, self.rate, self.speedup)
                if not await self._wait(step):
                    return self.sent
            else:
                self.schedule.delay(0.0)
            payload = message.build_replay_message(
                item.feature,
                extraction_id=self.extraction_id,
                replayed_at=self.now(),
                run=self.run_id,
                synthetic_case=item.synthetic_case,
            )
            try:
                await self.producer.send_and_wait(
                    self.topic,
                    value=message.encode(payload),
                    key=str(item.event_id).encode("utf-8"),
                )
            except Exception as error:  # Kafka failure: stop, publish nothing else.
                self._status("failed", f"{type(error).__name__}: {error}")
                return self.sent
            self.sent += 1
            previous = item
            if self.clock() - self._last_status >= STATUS_PERIOD_SECONDS:
                self._status("running")
        self._status("finished")
        return self.sent


async def run_replay(
    producer: KafkaProducer,
    items: Sequence[ReplayItem],
    *,
    topic: str,
    extraction_id: int | None,
    rate: float | None,
    speedup: float | None,
    control_dir: str | Path,
    lock: ReplayLock | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    run_id: str | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> int:
    """Publish `items` in order and return how many Kafka confirmed."""
    run = _Run(
        producer,
        items,
        topic=topic,
        extraction_id=extraction_id,
        rate=rate,
        speedup=speedup,
        control_dir=control_dir,
        lock=lock,
        clock=clock,
        sleep=sleep,
        run_id=run_id or uuid.uuid4().hex,
        now=now,
    )
    return await run.execute()
