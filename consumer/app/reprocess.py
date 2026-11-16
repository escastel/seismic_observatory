"""Reprocess the quarantine with the current rules (specs/004-consumer-quality/contracts/reprocess.md).

For every quarantine row with reprocessed_at NULL, in core and in replay, the message is
rebuilt from payload or raw_text, evaluated again and written in one transaction with the
search_path of the row's topic. Nothing is deleted: the quarantine row and the attempt 0 row
of message_log stay; the quarantine row is marked and an attempt 1 row is added.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

import asyncpg

from common import settings as common_settings
from common.db import create_pool
from common.logging import configure
from common.settings import TopicNames
from common.topics import UnknownTopicError, search_path_for

from .main import PERMANENT_DATABASE_ERRORS, source_for
from .persistence import Position, store_exclusion, store_version
from .rules import Accepted, Exclusion, Quarantine, evaluate
from .spatial import SpatialEnricher

logger = logging.getLogger(__name__)

SCOPES = ("core", "replay, core")

PENDING_SQL = "SELECT quarantine_id FROM quarantine WHERE reprocessed_at IS NULL ORDER BY quarantine_id"
# Waits for a concurrent run on the same row; once that run commits the row no longer matches.
LOCK_SQL = """
SELECT quarantine_id, kafka_topic, kafka_partition, kafka_offset, event_id, payload, raw_text
FROM quarantine WHERE quarantine_id = $1 AND reprocessed_at IS NULL FOR UPDATE
"""
MARK_SQL = """
UPDATE quarantine SET reprocessed_at = now(), reprocess_result = $2, reprocess_reason_codes = $3
WHERE quarantine_id = $1
"""
LOG_SQL = """
INSERT INTO message_log (kafka_topic, kafka_partition, kafka_offset, event_id, updated_at, outcome, produced_at, attempt)
VALUES ($1, $2, $3, $4, $5, $6, $7, 1)
ON CONFLICT (kafka_topic, kafka_partition, kafka_offset, attempt) DO NOTHING
"""


class _DryRun(Exception):
    """Raised at the end of a dry-run transaction to roll it back."""


@dataclass
class Summary:
    pending: int = 0
    recovered: int = 0
    still_rejected: int = 0
    skipped: int = 0
    by_space: dict[str, dict[str, int]] = field(default_factory=dict)

    def count(self, space: str, key: str) -> None:
        bucket = self.by_space.setdefault(space, {"pendientes": 0, "recuperadas": 0, "siguen rechazadas": 0})
        bucket[key] += 1


def rebuild(payload: Any, raw_text: str | None) -> bytes:
    """The message as it arrived: payload (jsonb) when it was JSON, raw_text otherwise."""
    if payload is not None:
        decoded = json.loads(payload) if isinstance(payload, str) else payload
        return json.dumps(decoded, ensure_ascii=False).encode("utf-8")
    return (raw_text or "").encode("utf-8")


def _produced_at(message: Any) -> datetime | None:
    value = message.get("ingested_at") if isinstance(message, dict) else None
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _extraction_id(message: Any) -> int | None:
    value = message.get("extraction_id") if isinstance(message, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


async def _decide(
    conn: asyncpg.Connection,
    row: asyncpg.Record,
    raw: bytes,
    topics: TopicNames,
    spatial: Any,
    replayed: bool,
) -> tuple[str, list[str] | None, str | None, datetime | None, str]:
    """Apply the current rules; returns (result, reasons, event_id, updated_at, log_outcome)."""
    position = Position(row["kafka_topic"], row["kafka_partition"], row["kafka_offset"])
    outcome = evaluate(raw, datetime.now(timezone.utc))
    decoded: Any = None
    try:
        decoded = json.loads(raw, parse_constant=lambda name: None)
    except ValueError:
        pass
    if isinstance(outcome, Quarantine):
        return "still_rejected", outcome.reasons, outcome.event_id, None, "quarantined"
    if isinstance(outcome, Exclusion):
        known = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM excluded_event WHERE event_id = $1 AND updated_at = $2)",
            outcome.event_id, outcome.updated_at,
        )
        await store_exclusion(conn, outcome, _extraction_id(decoded))
        result = "recovered_duplicate" if known else "recovered_new"
        return result, None, outcome.event_id, outcome.updated_at, "excluded"

    assert isinstance(outcome, Accepted)
    country_id, ambiguous = spatial.lookup(outcome.event.longitude, outcome.event.latitude)
    flags = sorted({*outcome.flags, "ambiguous_country"}) if ambiguous else outcome.flags
    event = outcome.event
    try:
        async with conn.transaction():  # savepoint: a model refusal must not abort the row's transaction
            applied = await store_version(
                conn, position, event,
                source=source_for(position.topic, topics),
                country_id=country_id, flags=flags, original=outcome.original,
                replayed_at=datetime.now(timezone.utc) if replayed else None,
            )
    except PERMANENT_DATABASE_ERRORS:
        return "still_rejected", ["model_constraint_violation"], event.external_id, None, "quarantined"
    return f"recovered_{applied}", None, event.external_id, event.updated, applied


async def reprocess_row(
    pool: asyncpg.Pool, quarantine_id: int, topics: TopicNames, spatial: Any, *, dry_run: bool = False
) -> tuple[str, str | None, list[str] | None] | None:
    """One row in one transaction; None when it is gone or already reprocessed."""
    async with pool.acquire() as conn:
        try:
            async with conn.transaction():
                row = await conn.fetchrow(LOCK_SQL, quarantine_id)
                if row is None:
                    return None
                scope = search_path_for(row["kafka_topic"], topics)
                raw = rebuild(row["payload"], row["raw_text"])
                result, reasons, event_id, updated_at, log_outcome = await _decide(
                    conn, row, raw, topics, spatial, replayed=scope.startswith("replay")
                )
                try:
                    decoded = json.loads(raw, parse_constant=lambda name: None)
                except ValueError:
                    decoded = None
                await conn.execute(
                    LOG_SQL, row["kafka_topic"], row["kafka_partition"], row["kafka_offset"],
                    event_id, updated_at, log_outcome, _produced_at(decoded),
                )
                await conn.execute(MARK_SQL, quarantine_id, result, reasons)
                if dry_run:
                    raise _DryRun
        except _DryRun:
            pass
        return result, event_id, reasons


async def reprocess(
    pools: Mapping[str, asyncpg.Pool],
    topics: TopicNames,
    spatial: Any,
    *,
    dry_run: bool = False,
    out: Callable[[str], None] = print,
) -> Summary:
    summary = Summary()
    for scope in SCOPES:
        pool = pools[scope]
        space = "replay" if scope.startswith("replay") else "core"
        async with pool.acquire() as conn:
            ids = [record["quarantine_id"] for record in await conn.fetch(PENDING_SQL)]
        for quarantine_id in ids:
            summary.pending += 1
            summary.count(space, "pendientes")
            try:
                done = await reprocess_row(pool, quarantine_id, topics, spatial, dry_run=dry_run)
            except UnknownTopicError as exc:
                summary.skipped += 1
                out(f"[{space}] fila {quarantine_id}: omitida ({exc})")
                continue
            if done is None:  # another run took it
                continue
            result, event_id, reasons = done
            prefix = "SIMULACION " if dry_run else ""
            detail = f" motivos={','.join(reasons)}" if reasons else ""
            out(f"{prefix}[{space}] fila {quarantine_id} evento={event_id} -> {result}{detail}")
            if result == "still_rejected":
                summary.still_rejected += 1
                summary.count(space, "siguen rechazadas")
            else:
                summary.recovered += 1
                summary.count(space, "recuperadas")
    out(
        f"Resumen: pendientes={summary.pending} recuperadas={summary.recovered} "
        f"siguen rechazadas={summary.still_rejected}"
        + (f" omitidas={summary.skipped}" if summary.skipped else "")
        + (" (simulacion: no se escribio nada)" if dry_run else "")
    )
    for space, counts in sorted(summary.by_space.items()):
        out("  " + space + ": " + " ".join(f"{key}={value}" for key, value in counts.items()))
    return summary


async def run(dry_run: bool) -> int:
    config = common_settings.consumer()
    spatial = SpatialEnricher(config.countries_path)
    pools: dict[str, asyncpg.Pool] = {}
    try:
        for scope in SCOPES:
            pools[scope] = await create_pool(config.database, scope, application_name="quality-reprocess", max_size=2)
        await reprocess(pools, config.kafka.topics, spatial, dry_run=dry_run)
        return 0
    except (asyncpg.PostgresError, OSError) as exc:
        logger.error("Database failure, what was done is kept; run again to continue: %s", exc)
        return 1
    finally:
        for pool in pools.values():
            await pool.close()


def main(argv: list[str] | None = None) -> None:
    configure("quality-reprocess")
    args = sys.argv[1:] if argv is None else argv
    sys.exit(asyncio.run(run("--dry-run" in args)))


if __name__ == "__main__":
    main()
