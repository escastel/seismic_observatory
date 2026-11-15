"""Ingestion gaps: periods the 24-hour feed did not cover (spec 003, US4, research R10).

A gap is derived from core.extraction alone, so nothing new is stored:

- closed: two consecutive successful feed requests (ok or not_modified) more
  than 24 hours apart. Uncovered events occurred in
  [previous - margin, next - 24 h + margin).
- open: the last successful request is more than 24 hours old; the gap ends at
  now - 24 h + margin.

The margin (GAP_MARGIN_MINUTES) absorbs USGS publication delays. A gap is
recovered when successful gap_recovery downloads cover it. Recovery is never
automatic: the producer only warns with the exact command (decision of
2026-11-15; the assignment asks to explain how the gap is recovered).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import asyncpg

from common.settings import CatalogLoaderSettings

FEED_WINDOW = timedelta(hours=24)


@dataclass(frozen=True)
class Gap:
    start: datetime
    end: datetime
    last_before: datetime            # last successful feed request before the gap
    next_after: datetime | None      # first one after it; None while the gap is still open


def _floor_minute(moment: datetime) -> datetime:
    return moment.replace(second=0, microsecond=0)


def _ceil_minute(moment: datetime) -> datetime:
    floored = _floor_minute(moment)
    return floored if floored == moment else floored + timedelta(minutes=1)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def gap_between(previous: datetime, following: datetime | None, now: datetime, margin: timedelta) -> Gap:
    """The uncovered period between two successful requests (following None: still open)."""
    end = (following if following is not None else now) - FEED_WINDOW + margin
    return Gap(_floor_minute(previous - margin), _ceil_minute(end), previous, following)


def find_gaps(successful_requests: Sequence[datetime], now: datetime, margin: timedelta) -> list[Gap]:
    """Gaps between consecutive successful feed requests, plus an open one at the end."""
    requests = sorted(successful_requests)
    gaps = [gap_between(previous, following, now, margin)
            for previous, following in zip(requests, requests[1:]) if following - previous > FEED_WINDOW]
    if requests and now - requests[-1] > FEED_WINDOW:
        gaps.append(gap_between(requests[-1], None, now, margin))
    return gaps


def is_covered(gap: Gap, windows: Sequence[tuple[datetime, datetime]]) -> bool:
    """True when the union of the [start, end) windows contains the whole gap."""
    cursor = gap.start
    for start, end in sorted(windows):
        if start > cursor:
            break
        cursor = max(cursor, end)
        if cursor >= gap.end:
            return True
    return cursor >= gap.end


def recovery_command(gap: Gap) -> str:
    return (f"docker compose run --rm catalog-loader --purpose gap_recovery "
            f"--start {_iso(gap.start)} --end {_iso(gap.end)}")


def warning_line(gap: Gap) -> str:
    """Stable text of the producer's start-up warning (contracts/catalog-loader.md)."""
    return (f"Ingestion gap detected: last successful feed request at {_iso(gap.last_before)}; "
            f"events between {_iso(gap.start)} and {_iso(gap.end)} are not covered by the feed. "
            f"Recover with: {recovery_command(gap)}")


# ------------------------------------------------------------------ database

GAP_BOUNDARIES = """
SELECT previous, requested_at
FROM (
    SELECT requested_at, lag(requested_at) OVER (ORDER BY requested_at) AS previous
    FROM extraction
    WHERE source = 'usgs_feed' AND outcome IN ('ok', 'not_modified')
) AS feed
WHERE requested_at - previous > interval '24 hours'
ORDER BY requested_at
"""

LAST_SUCCESSFUL = """
SELECT max(requested_at) FROM extraction WHERE source = 'usgs_feed' AND outcome IN ('ok', 'not_modified')
"""

RECOVERY_WINDOWS = """
SELECT window_start, window_end
FROM extraction
WHERE purpose = 'gap_recovery' AND outcome = 'ok' AND request_params ->> 'endpoint' = 'query'
  AND window_start IS NOT NULL AND window_end IS NOT NULL
"""


async def detect(conn: asyncpg.Connection, now: datetime, margin: timedelta) -> list[tuple[Gap, bool]]:
    """Every gap of the feed history with whether it has been recovered.

    Each closed gap comes straight from a pair of consecutive requests found
    by the window function; rebuilding them from the boundaries alone would
    lose the requests in between and invent gaps.
    """
    gaps = [gap_between(row["previous"], row["requested_at"], now, margin) for row in await conn.fetch(GAP_BOUNDARIES)]
    still_open = await open_gap(conn, now, margin)
    if still_open is not None:
        gaps.append(still_open)
    windows = [(row["window_start"], row["window_end"]) for row in await conn.fetch(RECOVERY_WINDOWS)]
    return [(gap, is_covered(gap, windows)) for gap in gaps]


async def open_gap(conn: asyncpg.Connection, now: datetime, margin: timedelta) -> Gap | None:
    """The gap that ends now, if the last successful request is more than 24 hours old."""
    last = await conn.fetchval(LAST_SUCCESSFUL)
    gaps = find_gaps([last], now, margin) if last is not None else []
    return gaps[0] if gaps else None


async def report_gaps(settings: CatalogLoaderSettings, pool: asyncpg.Pool, out: Callable[[str], None],
                      now: datetime | None = None) -> int:
    """catalog-loader --gaps: list the gaps and how to recover the pending ones."""
    now = now or datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        gaps = await detect(conn, now, timedelta(minutes=settings.gap_margin_minutes))
    if not gaps:
        out("No ingestion gaps: the feed has never been stopped for more than 24 hours.")
        return 0
    for gap, covered in gaps:
        state = "recuperado" if covered else "PENDIENTE"
        out(f"{_iso(gap.start)} → {_iso(gap.end)}  {state}")
        if not covered:
            out(f"    {recovery_command(gap)}")
    return 0
