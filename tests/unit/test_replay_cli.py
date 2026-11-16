"""Arguments, exit codes and messages of the replay command (contracts/replay-cli.md)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from common.settings import ReplaySettings
from producer.app.replay import cli, control, isolation
from producer.app.replay.selection import Selection, SelectionRejected

BASE = ["--start", "2025-01-01", "--end", "2025-02-01", "--min-mag", "4"]


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


# ------------------------------------------------------------------- arguments


def test_valid_start_request() -> None:
    request = cli.parse_request(["start", *BASE, "--bbox", "-10,-5,10.5,5", "--rate", "20", "--speedup", "3600"])

    assert request.command == "start"
    assert (request.start, request.end) == (utc(2025, 1, 1), utc(2025, 2, 1))
    assert request.min_mag == 4.0
    assert request.bbox == (-10.0, -5.0, 10.5, 5.0)
    assert (request.rate, request.speedup) == (20.0, 3600.0)


def test_rate_and_speedup_default_to_none() -> None:
    request = cli.parse_request(["start", *BASE])

    assert request.rate is None and request.speedup is None and request.bbox is None


def test_iso_instants_with_zone() -> None:
    request = cli.parse_request(["select", "--start", "2025-01-01T00:00:00Z", "--end", "2025-01-01T05:00:00+02:00",
                                 "--min-mag", "5"])

    assert request.end == utc(2025, 1, 1, 3)


@pytest.mark.parametrize(
    "extra, fragment",
    [
        (["--rate", "0"], "--rate debe ser mayor que cero"),
        (["--rate", "-3"], "--rate debe ser mayor que cero"),
        (["--rate", "nan"], "finito"),
        (["--speedup", "inf"], "finito"),
        (["--speedup", "abc"], "debe ser un número"),
        (["--bbox", "10,0,-10,5"], "min_lon"),
        (["--bbox", "0,10,5,-10"], "min_lat"),
        (["--bbox", "1,2,3"], "cuatro números"),
        (["--bbox", "a,b,c,d"], "--bbox"),
        (["--bbox", "0,0,200,5"], "fuera de"),
    ],
)
def test_invalid_options(extra: list[str], fragment: str) -> None:
    with pytest.raises(cli.UsageError) as error:
        cli.parse_request(["start", *BASE, *extra])

    assert fragment in str(error.value)


@pytest.mark.parametrize(
    "start, end",
    [("2025-02-01", "2025-01-01"), ("2025-01-01", "2025-01-01")],
)
def test_end_must_follow_start(start: str, end: str) -> None:
    with pytest.raises(cli.UsageError, match="posterior al inicio"):
        cli.parse_request(["select", "--start", start, "--end", end, "--min-mag", "4"])


def test_malformed_date_and_magnitude() -> None:
    with pytest.raises(cli.UsageError, match="fecha ilegible"):
        cli.parse_request(["select", "--start", "ayer", "--end", "2025-01-02", "--min-mag", "4"])
    with pytest.raises(cli.UsageError, match="--min-mag"):
        cli.parse_request(["select", "--start", "2025-01-01", "--end", "2025-01-02", "--min-mag", "x"])


def test_missing_option_and_missing_command() -> None:
    with pytest.raises(cli.UsageError):
        cli.parse_request(["start", "--start", "2025-01-01"])
    with pytest.raises(cli.UsageError):
        cli.parse_request([])


# ------------------------------------------------------------------ fake world


class FakeConn:
    def __init__(self, log: list[str] | None = None) -> None:
        self.log = log

    async def execute(self, sql: str, *args: Any) -> None:
        if self.log is not None:
            self.log.append(sql)


class FakeLock:
    def __init__(self, world: Any) -> None:
        self.world = world

    async def acquire(self) -> bool:
        self.world.events.append("lock")
        return not self.world.busy

    async def release(self) -> None:
        self.world.events.append("unlock")


class FakePool:
    def __init__(self) -> None:
        self.closed = False
        self.sql: list[str] = []

    def acquire(self) -> Any:
        pool = self

        class _Ctx:
            async def __aenter__(self) -> FakeConn:
                return FakeConn(pool.sql)

            async def __aexit__(self, *exc: Any) -> None:
                return None

        return _Ctx()

    async def close(self) -> None:
        self.closed = True


class FakeProducer:
    def __init__(self) -> None:
        self.started = self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True


def feature(event_id: str, time_ms: int) -> dict[str, Any]:
    return {"id": event_id, "properties": {"time": time_ms, "mag": 5.0}, "geometry": {"coordinates": [0, 0, 1]}}


class World:
    """Records every effect; knobs choose the failure to simulate."""

    def __init__(self, tmp_path: Path, features: list[dict[str, Any]] | None = None) -> None:
        self.tmp = tmp_path
        self.features = [feature("a", 1), feature("b", 2)] if features is None else features
        self.out: list[str] = []
        self.err: list[str] = []
        self.published: list[tuple[Any, ...]] = []
        self.counts: list[tuple[int, int]] = []
        self.registered = 0
        self.pool = FakePool()
        self.producer = FakeProducer()
        self.busy = False
        self.events: list[str] = []
        self.items: list[Any] = []
        self.reject: Exception | None = None
        self.run_state = "finished"
        self.snapshot_now: dict[str, Any] = {"tables": {"t": {"rows": 1, "checksum": "1"}}, "replay_selection_rows": 0}

    def deps(self) -> cli.Deps:
        settings = ReplaySettings(
            database=SimpleNamespace(), kafka=SimpleNamespace(topics=SimpleNamespace(replay="earthquakes.replay")),
            data_dir=str(self.tmp), default_rate=50.0,
        )

        async def create_pool(_: Any) -> FakePool:
            return self.pool

        async def ensure_topics(_: Any) -> list[str]:
            return []

        async def locate_files(*args: Any) -> list[Path]:
            if self.reject is not None:
                raise self.reject
            return [Path("f.json")]

        def select_events(files: Any, start: datetime, end: datetime, min_mag: float, bbox: Any) -> Selection:
            return Selection(start, end, min_mag, bbox, ("f.json",), list(self.features))

        async def register(conn: Any, chosen: Selection) -> int:
            self.events.append("register")
            self.registered += 1
            return 77

        async def set_count(conn: Any, extraction_id: int, published: int) -> None:
            self.counts.append((extraction_id, published))

        async def run_replay(producer: Any, items: Any, **kwargs: Any) -> int:
            self.published.append((len(items), kwargs))
            self.items = list(items)
            sent = len(items) if self.run_state == "finished" else 1
            control.write_status(kwargs["control_dir"], state=self.run_state, error="boom")
            return sent

        async def take_snapshot(conn: Any) -> dict[str, Any]:
            return self.snapshot_now

        return cli.Deps(
            load_settings=lambda: settings, create_pool=create_pool, ensure_topics=ensure_topics,
            make_producer=lambda s: self.producer, make_lock=lambda s: FakeLock(self), locate_files=locate_files, select_events=select_events,
            register_selection=register, set_published_count=set_count, run_replay=run_replay,
            take_snapshot=take_snapshot, out=self.out.append, err=self.err.append,
        )


def run(world: World, *argv: str) -> int:
    return cli.main(list(argv), world.deps())


# -------------------------------------------------------------------- commands


def test_select_registers_but_does_not_publish(tmp_path: Path) -> None:
    world = World(tmp_path)

    assert run(world, "select", *BASE) == 0
    assert world.registered == 1
    assert world.published == [] and not world.producer.started and world.counts == []
    text = "\n".join(world.out)
    assert "2 eventos" in text and "extraction_id 77" in text and world.pool.closed


def test_start_publishes_and_records_count(tmp_path: Path) -> None:
    world = World(tmp_path)

    assert run(world, "start", *BASE, "--speedup", "60") == 0
    count, kwargs = world.published[0]
    assert count == 2 and kwargs["topic"] == "earthquakes.replay" and kwargs["extraction_id"] == 77
    assert kwargs["rate"] == 50.0 and kwargs["speedup"] == 60.0
    assert world.counts == [(77, 2)] and world.producer.stopped
    assert "2 eventos publicados" in world.out[-1]


def test_start_explicit_rate_overrides_default(tmp_path: Path) -> None:
    world = World(tmp_path)

    run(world, "start", *BASE, "--rate", "5")

    assert world.published[0][1]["rate"] == 5.0


def test_empty_selection_exits_zero_with_warning(tmp_path: Path) -> None:
    world = World(tmp_path, features=[])

    assert run(world, "start", *BASE) == 0
    assert world.published == [] and not world.producer.started
    assert any("vacía" in line for line in world.out)


def test_usage_error_exit_1_in_spanish(tmp_path: Path) -> None:
    world = World(tmp_path)

    assert run(world, "start", *BASE, "--rate", "0") == 1
    assert world.err[0].startswith("replay: --rate debe ser mayor que cero")
    assert world.registered == 0 and not world.pool.closed


def test_selection_rejected_exit_2(tmp_path: Path) -> None:
    world = World(tmp_path)
    world.reject = SelectionRejected("El periodo no está cubierto")

    assert run(world, "start", *BASE) == 2
    assert world.err[0].startswith("Selección rechazada: El periodo no está cubierto")
    assert world.published == [] and world.pool.closed


def test_kafka_failure_during_run_exit_5(tmp_path: Path) -> None:
    world = World(tmp_path)
    world.run_state = "failed"

    assert run(world, "start", *BASE) == 5
    assert "fallo de Kafka" in world.err[0] and world.counts == [(77, 1)]


def test_infrastructure_exception_exit_5(tmp_path: Path) -> None:
    world = World(tmp_path)
    deps = world.deps()

    async def boom(_: Any) -> Any:
        raise OSError("sin base")

    deps.create_pool = boom

    assert cli.main(["select", *BASE], deps) == 5
    assert "fallo de la base o de Kafka" in world.err[0]


def test_snapshot_then_compare(tmp_path: Path) -> None:
    world = World(tmp_path)

    assert run(world, "snapshot") == 0
    assert (tmp_path / "replay" / cli.SNAPSHOT_NAME).is_file()
    assert run(world, "compare") == 0
    assert "idéntico" in world.out[-1]


def test_compare_with_differences_exit_6(tmp_path: Path) -> None:
    world = World(tmp_path)
    run(world, "snapshot")
    world.snapshot_now = {"tables": {"t": {"rows": 2, "checksum": "9"}}, "replay_selection_rows": 0}

    assert run(world, "compare") == 6
    assert "core.t" in "\n".join(world.err)


def test_compare_without_snapshot_exit_1(tmp_path: Path) -> None:
    world = World(tmp_path)

    assert run(world, "compare") == 1
    assert "replay snapshot" in world.err[0]
    assert isolation  # module under test is wired


# ------------------------------------------------------------- lock and control


def test_start_busy_exit_4_registers_and_publishes_nothing(tmp_path: Path) -> None:
    world = World(tmp_path)
    world.busy = True

    assert run(world, "start", *BASE) == 4
    assert world.registered == 0 and world.published == [] and not world.producer.started
    assert "Ya hay una reproducción activa" in world.err[0]


def test_start_takes_lock_before_registering_and_releases(tmp_path: Path) -> None:
    world = World(tmp_path)

    assert run(world, "start", *BASE) == 0
    assert world.events == ["lock", "register", "unlock"]


def test_start_releases_lock_on_failure(tmp_path: Path) -> None:
    world = World(tmp_path)
    world.reject = SelectionRejected("no")

    assert run(world, "start", *BASE) == 2
    assert world.events == ["lock", "unlock"]


@pytest.mark.parametrize("command", ["pause", "resume", "stop"])
def test_control_without_active_run_exit_3(tmp_path: Path, command: str) -> None:
    world = World(tmp_path)

    assert run(world, command) == 3
    assert control.read_control(tmp_path / "replay") is None
    assert "No hay ninguna reproducción activa" in world.err[0]
    control.write_status(tmp_path / "replay", state="finished")
    assert run(world, command) == 3


@pytest.mark.parametrize("state", ["running", "paused"])
@pytest.mark.parametrize("command", ["pause", "resume", "stop"])
def test_control_writes_order_when_active(tmp_path: Path, command: str, state: str) -> None:
    world = World(tmp_path)
    control.write_status(tmp_path / "replay", state=state)

    assert run(world, command) == 0
    assert control.read_control(tmp_path / "replay")["command"] == command


def test_status_prints_in_spanish(tmp_path: Path) -> None:
    world = World(tmp_path)
    assert run(world, "status") == 0 and "Sin reproducción" in world.out[-1]
    control.write_status(tmp_path / "replay", state="paused", sent=4, remaining=6, rate_target=50.0, speedup=None)

    assert run(world, "status") == 0
    assert world.out[-1] == "Estado: en pausa; enviados 4; restantes 6; objetivo 50.0 eventos/s"


def test_reset_busy_exit_4(tmp_path: Path) -> None:
    world = World(tmp_path)
    world.busy = True

    assert run(world, "reset") == 4
    assert world.pool.sql == []


def test_reset_free_calls_function(tmp_path: Path) -> None:
    world = World(tmp_path)

    assert run(world, "reset") == 0
    assert world.pool.sql == ["SELECT replay.reset()"] and world.events == ["lock", "unlock"]
    assert world.published == []


# ------------------------------------------------------------------- synthetic


def test_synthetic_appended_after_selection(tmp_path: Path) -> None:
    world = World(tmp_path)

    assert run(world, "start", *BASE, "--synthetic") == 0
    count, kwargs = world.published[0]
    assert count == 2 + 7 and kwargs["extraction_id"] == 77
    assert [i.event_id for i in world.items[:2]] == ["a", "b"]
    assert all(i.event_id.startswith("synthetic-replay-") for i in world.items[2:])
    assert world.counts == [(77, 9)]


def test_synthetic_only_registers_no_extraction(tmp_path: Path) -> None:
    world = World(tmp_path)

    assert run(world, "start", "--synthetic-only") == 0
    count, kwargs = world.published[0]
    assert count == 7 and kwargs["extraction_id"] is None
    assert world.registered == 0 and world.counts == []


@pytest.mark.parametrize("extra", [["--start", "2025-01-01"], ["--end", "2025-02-01"], ["--min-mag", "4"],
                                   ["--bbox=-10,0,10,5"], ["--synthetic"]])
def test_synthetic_only_incompatible_exit_1(tmp_path: Path, extra: list[str]) -> None:
    world = World(tmp_path)

    assert run(world, "start", "--synthetic-only", *extra) == 1
    assert world.registered == 0 and world.published == [] and world.events == []


def test_start_without_selection_options_exit_1(tmp_path: Path) -> None:
    world = World(tmp_path)

    assert run(world, "start") == 1
    assert run(world, "start", "--synthetic") == 1


def test_synthetic_only_keeps_rate_options() -> None:
    request = cli.parse_request(["start", "--synthetic-only", "--rate", "5"])

    assert request.synthetic_only and request.rate == 5.0 and request.start is None


def test_bbox_equals_form() -> None:
    assert cli.parse_request(["start", *BASE, "--bbox=-10,30,10,50"]).bbox == (-10.0, 30.0, 10.0, 50.0)
