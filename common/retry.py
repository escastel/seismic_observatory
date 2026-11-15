"""Retry with exponential backoff: 1 s, 2 s, 4 s ... capped at 30 s, forever."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterator
from typing import TypeVar

T = TypeVar("T")

INITIAL_DELAY = 1.0
MAX_DELAY = 30.0

logger = logging.getLogger(__name__)


def backoff_delays(initial: float = INITIAL_DELAY, maximum: float = MAX_DELAY) -> Iterator[float]:
    """Infinite sequence of waits: initial, doubled each time, never above maximum."""
    delay = initial
    while True:
        yield min(delay, maximum)
        delay = min(delay * 2, maximum)


async def retry(
    operation: Callable[[], Awaitable[T]],
    *,
    description: str,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    initial: float = INITIAL_DELAY,
    maximum: float = MAX_DELAY,
    sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
    log: logging.Logger | None = None,
) -> T:
    """Await operation() until it succeeds, waiting between failures.

    There is no attempt limit (contracts/runtime.md): a service keeps trying
    until its dependency comes back, and every failure is logged.
    """
    log = log or logger
    for attempt, delay in enumerate(backoff_delays(initial, maximum), start=1):
        try:
            return await operation()
        except retry_on as exc:
            log.warning("%s failed (attempt %d): %s; retrying in %.0f s", description, attempt, exc, delay)
            await sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover - backoff_delays is infinite
