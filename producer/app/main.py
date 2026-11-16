"""USGS producer: polls the live feed, records every request and publishes new versions.

One cycle (spec 003, data-model.md §7):

    request ─► extraction (+ original, exclusions) ─► publish new versions ─► published_count

- Every request is recorded in core.extraction, whatever its outcome (FR-001).
- The original is stored once per content fingerprint (FR-004, FR-005); a 304
  reuses the last one.
- If PostgreSQL fails after USGS answered, the result is kept and recorded as
  soon as the database is back, before asking USGS again (FR-001a).
- A version is marked as published only after Kafka confirmed it (FR-009);
  unconfirmed versions stay pending for the next cycle.
- Requests never start closer than PRODUCER_INTERVAL_SECONDS, and a long
  Retry-After is honoured (FR-007, FR-015).
- The heartbeat is written after every recorded cycle, also when USGS failed,
  but not while Kafka refuses messages (research R12).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import asyncpg
from aiokafka import AIOKafkaProducer

from common.db import create_pool
from common.health import Heartbeat
from common.logging import configure
from common.retry import retry
from common.settings import ProducerSettings
from common.topics import ensure_topics

from . import gaps, provenance
from .classify import Classified, Item, classify
from .config import load_config
from .fingerprint import bytes_fingerprint, features_fingerprint
from .provenance import Counts
from .publisher import publish_versions
from .usgs import FetchResult, fetch_async

logger = logging.getLogger(__name__)

SOURCE = "usgs_feed"
PURPOSE = "live"

# Failures of PostgreSQL itself: worth retrying the same cycle.
DATABASE_ERRORS: tuple[type[BaseException], ...] = (OSError, asyncpg.PostgresError, asyncpg.InterfaceError)


@dataclass
class FeedState:
    """What the producer remembers between cycles (lost on restart, by design)."""

    last_modified: str | None = None            # Last-Modified of the last 200, for If-Modified-Since
    last_fingerprint: str | None = None         # content of the last 200, reused by a 304
    pending_publish: list[Item] = field(default_factory=list)
    unrecorded: FetchResult | None = None       # USGS answered but PostgreSQL could not record it
    retry_after_until: float | None = None      # monotonic time before which USGS must not be asked


@dataclass(frozen=True)
class CycleReport:
    result: FetchResult
    extraction_id: int
    published: int
    publish_error: BaseException | None = None


Fetcher = Callable[..., Awaitable[FetchResult]]


def seconds_until_next_cycle(last_start: float, now: float, interval: float, retry_after_until: float | None) -> float:
    """Wait before the next request: a full interval after the last start, or later if USGS asked."""
    wait = last_start + interval - now
    if retry_after_until is not None:
        wait = max(wait, retry_after_until - now)
    return max(0.0, wait)


def _prepare(result: FetchResult, state: FeedState) -> tuple[str | None, Classified | None, Counts | None]:
    """Fingerprint, classification and counts of a result, per data-model.md §2."""
    if result.outcome == "ok":
        features = result.payload["features"]
        split = classify(features)
        counts = Counts(split.received, len(split.earthquakes), split.excluded_count)
        return features_fingerprint(features), split, counts
    if result.outcome == "not_modified":
        return state.last_fingerprint, None, None
    if result.outcome in ("invalid_json", "invalid_structure") and result.body is not None:
        return bytes_fingerprint(result.body), None, None
    return None, None, None


async def _record(pool: asyncpg.Pool, result: FetchResult, state: FeedState) -> tuple[int, Classified | None]:
    """Write the extraction, its original and its exclusions in one transaction."""
    fingerprint, split, counts = _prepare(result, state)
    async with pool.acquire() as conn:
        async with conn.transaction():
            extraction_id = await provenance.record_extraction(
                conn,
                result,
                source=SOURCE,
                purpose=PURPOSE,
                counts=counts,
                fingerprint=fingerprint,
                extra_detail=split.unidentifiable_detail() if split else None,
            )
            if result.outcome == "ok" and result.body is not None:
                await provenance.store_body(conn, fingerprint, result.body, seen_at=result.requested_at)
                await provenance.record_exclusions(conn, split.excluded, extraction_id)
            elif result.outcome == "not_modified" and fingerprint:
                await provenance.touch_payload(conn, fingerprint, seen_at=result.requested_at)
            elif fingerprint and result.body is not None:
                # Unreadable or malformed answer: kept as received for diagnosis (FR-006).
                await provenance.store_body(conn, fingerprint, result.body, seen_at=result.requested_at)
    if result.outcome == "ok":
        state.last_modified = result.last_modified
        state.last_fingerprint = fingerprint
    return extraction_id, split


async def _publish(
    config: ProducerSettings,
    producer: AIOKafkaProducer,
    pool: asyncpg.Pool,
    state: FeedState,
    extraction_id: int,
    earthquakes: list[Item],
    set_count: bool,
) -> tuple[int, BaseException | None]:
    candidates = earthquakes + state.pending_publish
    if not candidates:
        if set_count:
            async with pool.acquire() as conn:
                await provenance.set_published_count(conn, extraction_id, 0)
        return 0, None
    try:
        async with pool.acquire() as conn:
            outcome = await publish_versions(
                producer, conn, config.kafka.topics.live, candidates, source=SOURCE, extraction_id=extraction_id
            )
            state.pending_publish = outcome.pending
            if set_count or outcome.published:
                await provenance.set_published_count(conn, extraction_id, outcome.published)
    except DATABASE_ERRORS as exc:
        # PostgreSQL failed while publishing: nothing is lost, publish_state decides next time.
        state.pending_publish = candidates
        return 0, exc
    if outcome.error is not None:
        logger.warning("Kafka refused a message; %d version(s) left pending: %s", len(outcome.pending), outcome.error)
    return outcome.published, outcome.error


async def feed_cycle(
    config: ProducerSettings,
    producer: AIOKafkaProducer,
    pool: asyncpg.Pool,
    state: FeedState,
    fetcher: Fetcher = fetch_async,
) -> CycleReport:
    """One request to the feed, recorded and published. Raises only on database failure."""
    if state.unrecorded is None:
        state.unrecorded = await fetcher(
            config.feed_url, settings=config.usgs, if_modified_since=state.last_modified
        )
    result = state.unrecorded
    extraction_id, split = await _record(pool, result, state)   # raises if PostgreSQL is down
    state.unrecorded = None

    if result.retry_after_seconds:
        state.retry_after_until = time.monotonic() + result.retry_after_seconds

    published, error = 0, None
    if result.outcome == "ok":
        published, error = await _publish(config, producer, pool, state, extraction_id, split.earthquakes, True)
    elif result.outcome == "not_modified" and state.pending_publish:
        published, error = await _publish(config, producer, pool, state, extraction_id, [], False)

    logger.info(
        "Feed request %s: outcome=%s status=%s attempts=%d received=%s earthquakes=%s excluded=%s published=%d",
        extraction_id, result.outcome, result.http_status, result.attempt_count,
        split.received if split else "-", len(split.earthquakes) if split else "-",
        split.excluded_count if split else "-", published,
    )
    return CycleReport(result, extraction_id, published, error)


PURGE_EVERY = timedelta(hours=24)


def purge_due(last_purge: datetime | None, now: datetime) -> bool:
    """At start-up and then once every 24 hours (FR-033)."""
    return last_purge is None or now - last_purge >= PURGE_EVERY


async def purge_raw_payloads(pool: asyncpg.Pool, retention_days: int) -> int | None:
    """Delete feed bodies not seen for retention_days; file references and extractions stay.

    The count goes to the log, which FR-033 accepts as the record of each
    purge. A failure is logged and never stops the feed.
    """
    try:
        async with pool.acquire() as conn:
            purged = await conn.fetchval("SELECT core.purge_raw_payload($1)", retention_days)
    except DATABASE_ERRORS as exc:
        logger.warning("Raw payload purge failed, will try again in the next cycle: %s", exc)
        return None
    logger.info("Purged %d raw payload(s) not seen for more than %d days", purged, retention_days)
    return purged


async def startup_gap_warning(pool: asyncpg.Pool, now: datetime, margin_minutes: int) -> str | None:
    """Warning text when the feed was stopped for more than 24 hours (FR-028, FR-032).

    Only warns: the recovery is a manual command (FR-029), so the feed starts
    right away whatever the answer.
    """
    async with pool.acquire() as conn:
        gap = await gaps.open_gap(conn, now, timedelta(minutes=margin_minutes))
    return gaps.warning_line(gap) if gap else None


async def run(config: ProducerSettings) -> None:
    await retry(lambda: ensure_topics(config.kafka), description="creating Kafka topics", log=logger)
    pool = await create_pool(config.database, "core", application_name="producer", max_size=2)
    producer = AIOKafkaProducer(bootstrap_servers=config.kafka.bootstrap_servers, acks="all")
    await retry(producer.start, description="connecting to Kafka", log=logger)
    warning = await retry(
        lambda: startup_gap_warning(pool, datetime.now(timezone.utc), config.gap_margin_minutes),
        description="checking for ingestion gaps", retry_on=DATABASE_ERRORS, log=logger,
    )
    if warning:
        logger.warning(warning)
    heartbeat = Heartbeat()
    state = FeedState()
    last_purge: datetime | None = None
    try:
        while True:
            if purge_due(last_purge, datetime.now(timezone.utc)):
                if await purge_raw_payloads(pool, config.raw_payload_retention_days) is not None:
                    last_purge = datetime.now(timezone.utc)
            started = time.monotonic()
            report = await retry(
                lambda: feed_cycle(config, producer, pool, state),
                description="recording the feed request in PostgreSQL",
                retry_on=DATABASE_ERRORS,
                log=logger,
            )
            if report.publish_error is None:
                heartbeat.beat()
            await asyncio.sleep(
                seconds_until_next_cycle(started, time.monotonic(), config.interval_seconds, state.retry_after_until)
            )
    finally:
        await producer.stop()
        await pool.close()


def main() -> None:
    configure("producer")
    asyncio.run(run(load_config()))


if __name__ == "__main__":
    main()
