"""Offset guarantees of the consumer loop (principle II, research.md R20)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

pytest.importorskip("geopandas")

from aiokafka.structs import TopicPartition  # noqa: E402

from common.settings import ConsumerSettings, DatabaseSettings, KafkaSettings, TopicNames  # noqa: E402
from consumer.app.main import consume, consumer_options  # noqa: E402

PARTITION = TopicPartition("earthquakes.live", 0)


@dataclass
class FakeMessage:
    offset: int
    topic: str = "earthquakes.live"
    partition: int = 0
    value: bytes = b"{}"


class FakeConsumer:
    """Serves the given batches once, then signals the loop to stop."""

    def __init__(self, batches: list[list[FakeMessage]], stop: asyncio.Event, journal: list[str]) -> None:
        self.batches = batches
        self.stop = stop
        self.journal = journal

    async def getmany(self, *partitions, timeout_ms: int = 0, max_records: int | None = None) -> dict:
        if not self.batches:
            self.stop.set()
            return {}
        return {PARTITION: self.batches.pop(0)}

    async def commit(self, offsets=None) -> None:
        for partition, offset in offsets.items():
            assert partition == PARTITION
            self.journal.append(f"commit {offset}")


def run_loop(batches: list[list[FakeMessage]], handle) -> tuple[list[str], list[float]]:
    journal: list[str] = []
    waits: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    async def main() -> None:
        stop = asyncio.Event()
        consumer = FakeConsumer(batches, stop, journal)

        async def recording_handle(message: FakeMessage) -> str:
            try:
                outcome = await handle(message)
            except Exception:
                journal.append(f"fail {message.offset}")
                raise
            journal.append(f"{outcome} {message.offset}")
            return outcome

        await consume(consumer, recording_handle, stop=stop, sleep=fake_sleep)

    asyncio.run(main())
    return journal, waits


def test_consumer_is_configured_for_manual_commit_from_the_beginning() -> None:
    config = ConsumerSettings(
        database=DatabaseSettings("postgres", 5432, "observatory", "observatory_writer", "x"),
        kafka=KafkaSettings("kafka:9092", TopicNames(), 168),
        group_id="observatory-consumer",
        countries_path="/catalog/paises.geojson",
    )
    options = consumer_options(config)
    assert options["enable_auto_commit"] is False
    assert options["auto_offset_reset"] == "earliest"
    assert options["group_id"] == "observatory-consumer"


def test_each_offset_is_committed_after_its_message() -> None:
    async def handle(message: FakeMessage) -> str:
        return "new"

    journal, waits = run_loop([[FakeMessage(0), FakeMessage(1)], [FakeMessage(2)]], handle)

    assert journal == ["new 0", "commit 1", "new 1", "commit 2", "new 2", "commit 3"]
    assert waits == []


def test_failed_message_is_retried_and_nothing_later_is_committed() -> None:
    failures_left = {1: 2}

    async def handle(message: FakeMessage) -> str:
        if failures_left.get(message.offset):
            failures_left[message.offset] -= 1
            raise ConnectionError("database unavailable")
        return "new"

    journal, waits = run_loop([[FakeMessage(0), FakeMessage(1), FakeMessage(2)]], handle)

    assert journal == [
        "new 0",
        "commit 1",
        "fail 1",
        "fail 1",
        "new 1",
        "commit 2",
        "new 2",
        "commit 3",
    ]
    # No commit and no later message between the first failure and the success.
    first_failure = journal.index("fail 1")
    success = journal.index("new 1")
    assert all(entry.startswith("fail") for entry in journal[first_failure:success])
    assert waits == [1, 2]


def test_quarantined_message_counts_as_processed() -> None:
    async def handle(message: FakeMessage) -> str:
        return "quarantined" if message.offset == 0 else "new"

    journal, _ = run_loop([[FakeMessage(0), FakeMessage(1)]], handle)

    assert journal == ["quarantined 0", "commit 1", "new 1", "commit 2"]
