"""One active replay at a time (R4) and `replay reset` (contracts/replay-cli.md)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from common.settings import ReplaySettings
from producer.app.replay import cli
from producer.app.replay.isolation import compare, take_snapshot
from producer.app.replay.runner import ActiveRunLock
from tests.db.async_support import run_with_conn, writer_pool, writer_settings
from tests.db.helpers import Version, apply_version, count, utc


def lock_for(test_database: str) -> ActiveRunLock:
    return ActiveRunLock(writer_settings(test_database).dsn())


class FakeProducer:
    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass


def make_deps(test_database: str, tmp_path: Path, run_replay: Any = None) -> tuple[cli.Deps, list[str], list[str]]:
    settings = ReplaySettings(
        database=writer_settings(test_database),
        kafka=SimpleNamespace(topics=SimpleNamespace(replay="earthquakes.replay")),
        data_dir=str(tmp_path),
        default_rate=50.0,
    )
    out: list[str] = []
    err: list[str] = []

    async def noop(*args: Any, **kwargs: Any) -> list[str]:
        return []

    deps = cli.Deps(
        load_settings=lambda: settings,
        create_pool=lambda s: writer_pool(test_database),
        ensure_topics=noop,
        make_producer=lambda s: FakeProducer(),
        out=out.append,
        err=err.append,
    )
    if run_replay is not None:
        deps.run_replay = run_replay
    return deps, out, err


def test_lock_is_exclusive_and_released(test_database: str) -> None:
    async def body() -> None:
        first, second = lock_for(test_database), lock_for(test_database)
        assert await first.acquire() is True
        assert await first.acquire() is True  # idempotent while held
        assert await second.acquire() is False
        await first.release()
        assert await second.acquire() is True
        await second.release()

    asyncio.run(body())


def test_lock_is_freed_when_the_connection_dies(test_database: str) -> None:
    async def body() -> None:
        first, second = lock_for(test_database), lock_for(test_database)
        assert await first.acquire() is True
        await first._conn.close()  # the process dying closes the session without unlocking
        assert await second.acquire() is True
        await second.release()

    asyncio.run(body())


def test_second_start_gets_exit_4(test_database: str, tmp_path: Path) -> None:
    async def body() -> tuple[int, int, list[str]]:
        running, release = asyncio.Event(), asyncio.Event()

        async def slow_replay(producer: Any, items: Any, **kwargs: Any) -> int:
            assert await kwargs["lock"].acquire()
            running.set()
            await release.wait()
            return len(items)

        deps_a, _, _ = make_deps(test_database, tmp_path, slow_replay)
        deps_b, _, err_b = make_deps(test_database, tmp_path, slow_replay)
        request = cli.Request("start", synthetic_only=True)
        first = asyncio.create_task(cli.run(request, deps_a))
        await running.wait()
        second = await cli.run(request, deps_b)
        release.set()
        return await first, second, err_b

    first, second, err = asyncio.run(body())

    assert second == 4 and "Ya hay una reproducción activa" in err[0]
    assert first == 0
    # Finished: the lock is free again.
    assert asyncio.run(_acquire_and_release(lock_for(test_database))) is True


async def _acquire_and_release(lock: ActiveRunLock) -> bool:
    got = await lock.acquire()
    await lock.release()
    return got


def seed(connect: Any) -> None:
    core_conn = connect("writer", search_path="core")
    replay_conn = connect("writer", search_path="replay, core")
    for n in range(3):
        apply_version(core_conn, Version(f"K{n}", utc(f"2026-11-14 10:0{n}")))
        apply_version(replay_conn, Version(f"R{n}", utc(f"2026-11-14 11:0{n}")), replayed_at=utc("2026-11-14 12:00"))


def test_reset_with_lock_busy_exit_4(test_database: str, tmp_path: Path, connect: Any) -> None:
    seed(connect)
    deps, _, err = make_deps(test_database, tmp_path)

    async def body() -> int:
        holder = lock_for(test_database)
        assert await holder.acquire()
        try:
            return await cli.run(cli.Request("reset"), deps)
        finally:
            await holder.release()

    assert asyncio.run(body()) == 4

    assert "reset" in err[0]
    owner = connect("owner")
    assert count(owner, "replay.event_current") == 3


def test_reset_free_empties_replay_and_leaves_core(test_database: str, tmp_path: Path, connect: Any) -> None:
    seed(connect)
    before = run_with_conn(test_database, take_snapshot)
    deps, out, _ = make_deps(test_database, tmp_path)

    assert cli.main(["reset"], deps) == 0

    owner = connect("owner")
    for table in ("event_current", "event_version", "publish_state", "message_log", "quarantine", "excluded_event"):
        assert count(owner, f"replay.{table}") == 0, table
    assert compare(before, run_with_conn(test_database, take_snapshot)) == []
    assert before["tables"]["event_current"]["rows"] == 3
    assert "core no se ha tocado" in out[-1]
    # The lock was released by reset.
    assert asyncio.run(_acquire_and_release(lock_for(test_database))) is True


def test_core_has_no_reset_function(connect: Any) -> None:
    owner = connect("owner")
    names = owner.execute(
        "SELECT n.nspname, p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE p.proname = 'reset'"
    ).fetchall()

    assert [tuple(row) for row in names] == [("replay", "reset")]
