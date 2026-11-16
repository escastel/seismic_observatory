import asyncio

import pytest

from producer.app.replay import control
from producer.app.replay.runner import ReplayItem, RunLockBusy, run_replay
from tests.support.fake_kafka import FakeProducer


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_items(n: int, gap_ms: int = 10_000) -> list[ReplayItem]:
    return [
        ReplayItem(
            {
                "type": "Feature",
                "id": f"ev{i}",
                "properties": {"time": 1_700_000_000_000 + i * gap_ms, "updated": 1_700_000_500_000 + i, "mag": 4.5, "place": "X"},
                "geometry": {"type": "Point", "coordinates": [1, 2, 3]},
            }
        )
        for i in range(n)
    ]


def run(items, tmp_path, producer=None, clock=None, **kwargs):
    producer = producer or FakeProducer()
    clock = clock or FakeClock()
    params = dict(topic="earthquakes.replay", extraction_id=7, rate=50, speedup=None)
    params.update(kwargs)
    sent = asyncio.run(
        run_replay(producer, items, control_dir=tmp_path, clock=clock, sleep=clock.sleep, run_id="r1", **params)
    )
    return sent, producer, clock


def test_publishes_in_order_with_key_and_intact_fields(tmp_path):
    items = make_items(3)
    sent, producer, _ = run(items, tmp_path)
    assert sent == 3
    assert producer.keys("earthquakes.replay") == ["ev0", "ev1", "ev2"]
    for item, record in zip(items, producer.sent):
        assert record.value["time"] == item.time_ms
        assert record.value["updated"] == item.feature["properties"]["updated"]
        assert record.value["replayed_at"]
        assert record.value["replay_run"] == "r1"
        assert record.value["extraction_id"] == 7
        assert "synthetic" not in record.value
    status = control.read_status(tmp_path)
    assert status["state"] == "finished" and status["sent"] == 3 and status["remaining"] == 0


def test_synthetic_case_is_passed(tmp_path):
    item = ReplayItem(make_items(1)[0].feature, synthetic_case="dup")
    _, producer, _ = run([item], tmp_path)
    assert producer.sent[0].value["synthetic"] is True
    assert producer.sent[0].value["synthetic_case"] == "dup"


def test_rate_cadence_within_20_percent(tmp_path):
    _, _, clock = run(make_items(11), tmp_path, rate=10)
    assert len(clock.sleeps) == 10
    assert all(abs(s - 0.1) <= 0.02 for s in clock.sleeps)
    assert clock.now - 1000.0 == pytest.approx(1.0, rel=0.2)


def test_speedup_uses_original_gaps(tmp_path):
    _, _, clock = run(make_items(4, gap_ms=10_000), tmp_path, rate=None, speedup=100)
    assert clock.sleeps == pytest.approx([0.1, 0.1, 0.1])


def test_kafka_failure_midway(tmp_path):
    producer = FakeProducer(fail_after=2)
    sent, producer, _ = run(make_items(5), tmp_path, producer=producer)
    assert sent == 2
    assert len(producer.sent) == 2 and producer.attempts == 3
    status = control.read_status(tmp_path)
    assert status["state"] == "failed" and status["sent"] == 2 and status["remaining"] == 3
    assert "broker not available" in status["error"]


def test_empty_selection(tmp_path):
    sent, producer, _ = run([], tmp_path)
    assert sent == 0 and producer.attempts == 0
    status = control.read_status(tmp_path)
    assert status["state"] == "finished" and status["total"] == 0


class ControlClock(FakeClock):
    """FakeClock that runs actions when the fake time reaches given offsets."""

    def __init__(self, actions):
        super().__init__()
        self.actions = sorted(actions, key=lambda a: a[0])  # (offset seconds, callable)
        self.t0 = self.now

    async def sleep(self, seconds: float) -> None:
        await super().sleep(seconds)
        while self.actions and self.now - self.t0 >= self.actions[0][0]:
            self.actions.pop(0)[1]()


def test_stale_control_order_is_discarded(tmp_path):
    control.write_control(tmp_path, "stop")
    sent, _, _ = run(make_items(3), tmp_path)
    assert sent == 3
    assert control.read_status(tmp_path)["state"] == "finished"


def test_pause_no_sends_while_paused_then_resume_without_skips(tmp_path):
    items = make_items(6)
    producer = FakeProducer()
    snaps = []

    def snapshot():
        status = control.read_status(tmp_path)
        snaps.append((status["state"], status["sent"], len(producer.sent)))

    clock = ControlClock(
        [
            (2.1, lambda: control.write_control(tmp_path, "pause")),
            (3.0, snapshot),
            (20.0, snapshot),
            (21.0, lambda: control.write_control(tmp_path, "resume")),
        ]
    )
    sent, _, _ = run(items, tmp_path, producer=producer, clock=clock, rate=1)
    assert snaps[0] == snaps[1] and snaps[0][0] == "paused"
    assert sent == 6
    assert producer.keys("earthquakes.replay") == [i.event_id for i in items]
    assert control.read_status(tmp_path)["state"] == "finished"


def test_pause_reacts_within_poll_period(tmp_path):
    marks = {}

    class Probe(ControlClock):
        async def sleep(self, seconds):
            await super().sleep(seconds)
            if "at" in marks and "seen" not in marks and control.read_status(tmp_path)["state"] == "paused":
                marks["seen"] = self.now

    def pause():
        control.write_control(tmp_path, "pause")
        marks["at"] = clock.now

    clock = Probe([(1.0, pause), (4.0, lambda: control.write_control(tmp_path, "stop"))])
    run(make_items(10), tmp_path, clock=clock, rate=0.5)
    assert marks["seen"] - marks["at"] <= 0.25 + 1e-9
    assert marks["seen"] - marks["at"] < 2


def test_stop_while_running_keeps_published(tmp_path):
    clock = ControlClock([(2.5, lambda: control.write_control(tmp_path, "stop"))])
    sent, producer, _ = run(make_items(10), tmp_path, clock=clock, rate=1)
    status = control.read_status(tmp_path)
    assert status["state"] == "stopped"
    assert sent == len(producer.sent) == status["sent"] and 0 < sent < 10
    assert producer.keys("earthquakes.replay") == [f"ev{i}" for i in range(sent)]


def test_stop_while_paused(tmp_path):
    clock = ControlClock(
        [
            (1.5, lambda: control.write_control(tmp_path, "pause")),
            (5.0, lambda: control.write_control(tmp_path, "stop")),
        ]
    )
    sent, producer, _ = run(make_items(10), tmp_path, clock=clock, rate=1)
    status = control.read_status(tmp_path)
    assert status["state"] == "stopped" and status["sent"] == sent == len(producer.sent) < 10


class FakeLock:
    def __init__(self, free: bool = True) -> None:
        self.free, self.acquired, self.released = free, 0, 0

    async def acquire(self) -> bool:
        self.acquired += 1
        return self.free

    async def release(self) -> None:
        self.released += 1


def test_lock_acquired_and_released_after_run(tmp_path):
    lock = FakeLock()
    sent, _, _ = run(make_items(2), tmp_path, lock=lock)
    assert sent == 2 and (lock.acquired, lock.released) == (1, 1)


def test_lock_released_when_kafka_fails(tmp_path):
    class Broken:
        async def send_and_wait(self, *a, **k):
            raise RuntimeError("boom")

    lock = FakeLock()
    sent, _, _ = run(make_items(2), tmp_path, producer=Broken(), lock=lock)
    assert sent == 0 and lock.released == 1


def test_busy_lock_raises_and_publishes_nothing(tmp_path):
    lock = FakeLock(free=False)
    producer = FakeProducer()
    with pytest.raises(RunLockBusy):
        run(make_items(2), tmp_path, producer=producer, lock=lock)
    assert producer.sent == [] and lock.released == 0
