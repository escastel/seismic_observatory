"""Planning of catalog requests: months, subdivision and parameters (FR-019, research R8).

The USGS FDSN service answers HTTP 400 when a query matches more events than
maxAllowed (20 000) instead of truncating. The /count endpoint tells in
advance how many events an interval holds, so each interval is split in halves
until every part fits; nothing is ever accepted truncated. Bounds are
[starttime, endtime): an event exactly at a boundary belongs to the later part.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .usgs import FetchResult

LIMIT_EXCEEDED_TEXT = b"exceeds search limit"


class IntervalTooLarge(RuntimeError):
    """An interval of one second still holds more events than the source can return."""


def iso(moment: datetime) -> str:
    """UTC instant as USGS expects it: 2025-01-01T00:00:00Z."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _compact(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


@dataclass(frozen=True)
class Interval:
    start: datetime   # included
    end: datetime     # excluded

    @property
    def seconds(self) -> float:
        return (self.end - self.start).total_seconds()

    def halves(self) -> tuple[Interval, Interval]:
        middle = self.start + timedelta(seconds=int(self.seconds // 2))
        return Interval(self.start, middle), Interval(middle, self.end)

    def label(self) -> str:
        return f"{iso(self.start)} → {iso(self.end)}"


@dataclass(frozen=True)
class Filters:
    min_magnitude: float | None = 4.0
    event_type: str | None = "earthquake"

    def _magnitude(self) -> int | float:
        value = float(self.min_magnitude)
        return int(value) if value.is_integer() else value

    def count_params(self, interval: Interval) -> dict[str, Any]:
        params: dict[str, Any] = {"format": "geojson", "starttime": iso(interval.start), "endtime": iso(interval.end)}
        if self.min_magnitude is not None:
            params["minmagnitude"] = self._magnitude()
        if self.event_type is not None:
            params["eventtype"] = self.event_type
        return params

    def query_params(self, interval: Interval) -> dict[str, Any]:
        # Never "limit": a limit would truncate silently (enunciado §4.2).
        return {**self.count_params(interval), "orderby": "time-asc"}

    def tag(self) -> str:
        parts = []
        if self.min_magnitude is not None:
            parts.append(f"m{self._magnitude()}")
        if self.event_type is not None:
            parts.append(self.event_type.replace(" ", "-"))
        return "_".join(parts) or "all"

    def describe(self) -> str:
        magnitude = "todas las magnitudes" if self.min_magnitude is None else f"magnitud ≥ {self._magnitude()}"
        kind = "todos los tipos" if self.event_type is None else f"tipo {self.event_type}"
        return f"{magnitude} · {kind}"


def recorded_params(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    """What core.extraction.request_params keeps (data-model.md §2)."""
    return {"endpoint": endpoint, **params}


def file_name(interval: Interval, filters: Filters, fingerprint: str | None = None) -> str:
    """<start>_<end>_<filter>[_<first 12 hex of the SHA-256>].geojson.

    With the fingerprint in the name a stored file is never overwritten: a new
    download with different content (USGS regenerates metadata on every answer)
    gets its own file, so every recorded fingerprint always matches its file.
    """
    stem = f"{_compact(interval.start)}_{_compact(interval.end)}_{filters.tag()}"
    return f"{stem}_{fingerprint[:12]}.geojson" if fingerprint else f"{stem}.geojson"


def month_intervals(start: datetime, end: datetime) -> list[Interval]:
    """Calendar months covering [start, end); the first and last may be partial."""
    if end <= start:
        raise ValueError("the end of the period must be after its start")
    intervals = []
    cursor = start
    while cursor < end:
        following = datetime(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1, tzinfo=timezone.utc)
        intervals.append(Interval(cursor, min(following, end)))
        cursor = following
    return intervals


Counter = Callable[[Interval], Awaitable[tuple[int, int]]]


async def plan_intervals(interval: Interval, count: Counter) -> list[tuple[Interval, int]]:
    """Split interval until each part's declared count fits; returns (part, declared) in order."""
    declared, max_allowed = await count(interval)
    if declared <= max_allowed:
        return [(interval, declared)]
    if interval.seconds <= 1:
        raise IntervalTooLarge(
            f"{interval.label()} holds {declared} events, more than {max_allowed}, and cannot be split further"
        )
    first, second = interval.halves()
    return await plan_intervals(first, count) + await plan_intervals(second, count)


def limit_exceeded(result: FetchResult) -> bool:
    """The 400 USGS returns when the catalog grew past the maximum between /count and /query."""
    return result.http_status == 400 and bool(result.body) and LIMIT_EXCEEDED_TEXT in result.body
