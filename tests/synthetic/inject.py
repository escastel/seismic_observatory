"""Publish the synthetic cases to the live topic (contracts/reprocess.md).

    python -m tests.synthetic.inject [--list] [--batch N]

Cases already present in the database are skipped, so repeating the command adds
nothing. --batch N also publishes N valid synthetic events (restart test).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Callable, Sequence
from typing import Any, Protocol

import asyncpg

from tests.synthetic.cases import BATCH_PREFIX, CASES, PREFIX, SyntheticCase, restart_batch

PRESENT_SQL = """
SELECT EXISTS (SELECT 1 FROM quarantine
               WHERE payload->>'synthetic_case' = $1
                  OR position($2 in payload::text) > 0
                  OR position($2 in raw_text) > 0)
    OR EXISTS (SELECT 1 FROM event_version WHERE event_id = $2)
    OR EXISTS (SELECT 1 FROM excluded_event WHERE event_id = $2)
"""


class Producer(Protocol):
    async def send_and_wait(self, topic: str, value: bytes | None = None, key: bytes | None = None, **kwargs: Any) -> Any: ...


async def present_cases(conn: asyncpg.Connection, cases: Sequence[SyntheticCase]) -> set[str]:
    """Names of the cases that already left a trace in quarantine, history or exclusions."""
    return {case.case for case in cases if await conn.fetchval(PRESENT_SQL, case.case, case.event_id)}


async def present_batch_ids(conn: asyncpg.Connection) -> set[str]:
    rows = await conn.fetch("SELECT event_id FROM event_version WHERE event_id LIKE $1", BATCH_PREFIX + "%")
    return {row["event_id"] for row in rows}


def describe(case: SyntheticCase) -> str:
    return f"{case.case:<28} {case.outcome:<10} {','.join(case.codes):<40} {case.description}"


async def inject(
    producer: Producer,
    conn: asyncpg.Connection,
    topic: str,
    *,
    cases: Sequence[SyntheticCase] = CASES,
    batch: int = 0,
    out: Callable[[str], None] = print,
) -> tuple[int, int]:
    """Publish what is missing; returns (published, skipped)."""
    present = await present_cases(conn, cases)
    published = skipped = 0
    for case in cases:
        if case.case in present:
            skipped += 1
            continue
        await producer.send_and_wait(topic, value=case.raw(), key=case.event_id.encode("utf-8"))
        published += 1
    if batch:
        known = await present_batch_ids(conn)
        for message in restart_batch(batch):
            if message["id"] in known:
                skipped += 1
                continue
            await producer.send_and_wait(topic, value=json.dumps(message).encode(), key=message["id"].encode("utf-8"))
            published += 1
    out(f"Publicados {published}, omitidos (ya constan) {skipped}")
    return published, skipped


async def run(batch: int) -> None:
    from aiokafka import AIOKafkaProducer

    from common import settings as common_settings
    from common.db import create_pool
    from common.topics import ensure_topics

    kafka = common_settings.kafka()
    await ensure_topics(kafka)
    pool = await create_pool(common_settings.database("writer"), "core", application_name="synthetic-inject", max_size=1)
    producer = AIOKafkaProducer(bootstrap_servers=kafka.bootstrap_servers, acks="all")
    await producer.start()
    try:
        async with pool.acquire() as conn:
            await inject(producer, conn, kafka.topics.live, batch=batch)
    finally:
        await producer.stop()
        await pool.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m tests.synthetic.inject")
    parser.add_argument("--list", action="store_true", help="show every case with its expected outcome")
    parser.add_argument("--batch", type=int, default=0, metavar="N", help="also publish N valid synthetic events")
    args = parser.parse_args(argv)
    if args.list:
        for case in CASES:
            print(describe(case))
        print(f"(--batch N: N eventos validos {BATCH_PREFIX}NNNNN; prefijo reservado {PREFIX})")
        return
    asyncio.run(run(args.batch))


if __name__ == "__main__":
    main()
