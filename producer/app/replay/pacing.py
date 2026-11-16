"""Pacing of the historical replay (research R6).

- Only rate: interval = 1 / rate.
- With speedup: interval = original gap / speedup; if rate is also given,
  max(original / speedup, 1 / rate), so the cadence never exceeds the rate.
- Deadlines are absolute (monotonic clock) so the send delay does not
  accumulate; after a pause they are rebased to avoid catching up in bursts.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Awaitable, Callable


def _check_positive(name: str, value: float | None) -> None:
    if value is None:
        return
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} debe ser mayor que 0 y finito (recibido: {value!r})")


def interval(previous_time_ms: float, next_time_ms: float, rate: float | None, speedup: float | None) -> float:
    """Seconds between publishing two consecutive events."""
    _check_positive("rate", rate)
    _check_positive("speedup", speedup)
    if rate is None and speedup is None:
        raise ValueError("hay que indicar rate, speedup o ambos")
    if speedup is None:
        return 1.0 / rate  # type: ignore[operator]
    original = max((next_time_ms - previous_time_ms) / 1000.0, 0.0) / speedup
    if rate is None:
        return original
    return max(original, 1.0 / rate)


class Schedule:
    """Absolute deadlines over an injectable monotonic clock."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._deadline: float | None = None

    def delay(self, step: float) -> float:
        """Seconds to wait before the next event, which follows the previous by `step`.

        The first call returns 0 and anchors the schedule. If the deadline is
        already past (pause, slow send), it is rebased to now and 0 is returned.
        """
        now = self._clock()
        if self._deadline is None:
            self._deadline = now
            return 0.0
        self._deadline += max(step, 0.0)
        remaining = self._deadline - now
        if remaining < 0:
            self._deadline = now
            return 0.0
        return remaining

    async def wait(self, step: float, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        remaining = self.delay(step)
        if remaining > 0:
            await sleep(remaining)
