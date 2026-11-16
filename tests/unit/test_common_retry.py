"""Backoff of common.retry (contracts/runtime.md, «Salud y reintentos»)."""

from __future__ import annotations

import asyncio
from itertools import islice

import pytest

from common.retry import backoff_delays, retry


def test_delays_grow_exponentially_from_one_second_and_stop_at_thirty() -> None:
    assert list(islice(backoff_delays(), 8)) == [1, 2, 4, 8, 16, 30, 30, 30]


def test_retries_until_the_operation_succeeds() -> None:
    waits: list[float] = []
    calls = 0

    async def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls < 8:
            raise ConnectionError("not yet")
        return "ok"

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    assert asyncio.run(retry(flaky, description="test", sleep=fake_sleep)) == "ok"
    assert calls == 8
    assert waits == [1, 2, 4, 8, 16, 30, 30]


def test_errors_outside_retry_on_are_not_retried() -> None:
    async def broken() -> None:
        raise KeyError("bug")

    async def fake_sleep(seconds: float) -> None:
        raise AssertionError("must not wait")

    with pytest.raises(KeyError):
        asyncio.run(retry(broken, description="test", retry_on=(ConnectionError,), sleep=fake_sleep))


def test_each_failure_is_logged(caplog) -> None:
    calls = 0

    async def flaky() -> None:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ConnectionError("refused")

    async def fake_sleep(seconds: float) -> None:
        return None

    with caplog.at_level("WARNING"):
        asyncio.run(retry(flaky, description="connecting to Kafka", sleep=fake_sleep))
    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 2
    assert all("connecting to Kafka failed" in message and "refused" in message for message in messages)
