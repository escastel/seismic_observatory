import asyncio
import math

import pytest

from producer.app.replay.pacing import Schedule, interval


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_rate_only():
    assert interval(0, 5000, 50, None) == pytest.approx(0.02)


def test_speedup_only():
    assert interval(0, 10_000, None, 10) == pytest.approx(1.0)


def test_both_rate_caps_cadence():
    assert interval(0, 1000, 10, 100) == pytest.approx(0.1)  # 0.01 < 1/rate
    assert interval(0, 10_000, 10, 2) == pytest.approx(5.0)  # original wins


def test_negative_gap_is_zero():
    assert interval(5000, 1000, None, 2) == 0.0
    assert interval(5000, 1000, 10, 2) == pytest.approx(0.1)


@pytest.mark.parametrize("bad", [0, -1, math.nan, math.inf])
def test_invalid_values(bad):
    with pytest.raises(ValueError):
        interval(0, 1, bad, None)
    with pytest.raises(ValueError):
        interval(0, 1, None, bad)


def test_requires_rate_or_speedup():
    with pytest.raises(ValueError):
        interval(0, 1, None, None)


def test_schedule_absolute_deadlines_do_not_accumulate():
    clock = FakeClock()
    s = Schedule(clock)
    assert s.delay(1.0) == 0.0
    clock.now += 0.3  # send took 0.3 s
    assert s.delay(1.0) == pytest.approx(0.7)
    clock.now += 0.7 + 0.2
    assert s.delay(1.0) == pytest.approx(0.8)


def test_schedule_rebases_after_pause():
    clock = FakeClock()
    s = Schedule(clock)
    s.delay(1.0)
    clock.now += 60  # long pause
    assert s.delay(1.0) == 0.0
    assert s.delay(1.0) == pytest.approx(1.0)  # no burst
    assert s.delay(1.0) == pytest.approx(2.0)


def test_wait_uses_injected_sleep():
    clock = FakeClock()
    s = Schedule(clock)
    slept: list[float] = []

    async def fake_sleep(t: float) -> None:
        slept.append(t)

    async def run() -> None:
        await s.wait(2.0, fake_sleep)
        await s.wait(2.0, fake_sleep)

    asyncio.run(run())
    assert slept == [pytest.approx(2.0)]
