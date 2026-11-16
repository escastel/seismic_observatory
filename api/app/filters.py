"""Query filters shared by the map and the statistics, and the single WHERE builder.

Map and statistics MUST filter exactly the same events (constitution VII), so both build
their WHERE clause here. Values are always bound parameters, never interpolated.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

DEFAULT_WINDOW = timedelta(hours=24)
COUNTRY_ID_PATTERN = re.compile(r"^[A-Za-z0-9]{1,8}$")

# A synthetic event is marked twice by the consumer (spec 004): by its id prefix and by a
# quality flag. Either one is enough to treat it as synthetic.
SYNTHETIC_SQL = "(starts_with(f.event_id, 'synthetic-') OR 'synthetic' = ANY(f.quality_flags))"


class ParameterError(ValueError):
    """An invalid query parameter: the API answers 422 naming the parameter."""

    def __init__(self, param: str, message: str) -> None:
        super().__init__(f"{param}: {message}")
        self.param = param
        self.message = message


@dataclass(frozen=True)
class QueryFilters:
    mode: str = "live"
    start: datetime | None = None
    end: datetime | None = None
    min_mag: float | None = None
    country_id: str | None = None
    exclude_synthetic: bool = False


@dataclass(frozen=True)
class Where:
    """The WHERE clause and its bound values, plus the effective period it implies."""

    sql: str
    values: list[Any]
    period_start: datetime | None
    period_end: datetime | None
    default_applied: bool


def parse_filters(
    mode: str = "live",
    start: datetime | None = None,
    end: datetime | None = None,
    min_mag: float | None = None,
    country_id: str | None = None,
    exclude_synthetic: bool = False,
) -> QueryFilters:
    """Validate already-typed values; raise ParameterError naming the failing parameter."""
    if mode not in ("live", "replay"):
        raise ParameterError("mode", f"must be 'live' or 'replay', got {mode!r}")
    for name, value in (("start", start), ("end", end)):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ParameterError(name, "must be an ISO 8601 instant with a time zone, e.g. 2025-03-01T00:00:00Z")
    if start is not None and end is not None and start >= end:
        raise ParameterError("start", "must be earlier than end (start is inclusive, end is exclusive)")
    if min_mag is not None and not math.isfinite(min_mag):
        raise ParameterError("min_mag", "must be a finite number")
    if country_id is not None and not COUNTRY_ID_PATTERN.match(country_id):
        raise ParameterError("country_id", "must be 1 to 8 letters or digits, e.g. ESP")
    return QueryFilters(
        mode=mode,
        start=start,
        end=end,
        min_mag=min_mag,
        country_id=country_id,
        exclude_synthetic=exclude_synthetic,
    )


def effective_period(filters: QueryFilters, now: datetime) -> tuple[datetime | None, datetime | None, bool]:
    """The period the query covers and whether the default 24 hours were applied.

    Real data: without start, the 24 hours before end (or before now when end is absent).
    Replay data is historical, so no default window applies.
    """
    start, end = filters.start, filters.end
    if start is None and filters.mode == "live":
        return (end or now) - DEFAULT_WINDOW, end, True
    return start, end, False


def build_where(filters: QueryFilters, now: datetime, *, with_min_mag: bool = True) -> Where:
    """Single source of the filter. «f» is the alias of event_current in every query."""
    conditions: list[str] = []
    values: list[Any] = []

    def add(condition: str, value: Any) -> None:
        values.append(value)
        conditions.append(condition.replace("?", f"${len(values)}"))

    start, end, default_applied = effective_period(filters, now)
    if start is not None:
        add("f.event_time >= ?", start)
    if end is not None:
        add("f.event_time < ?", end)
    if with_min_mag and filters.min_mag is not None:
        add("f.magnitude >= ?", filters.min_mag)  # a null magnitude never satisfies it
    if filters.country_id is not None:
        add("f.country_id = ?", filters.country_id)
    if filters.mode == "live" or filters.exclude_synthetic:
        conditions.append(f"NOT {SYNTHETIC_SQL}")

    sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return Where(sql=sql, values=values, period_start=start, period_end=end, default_applied=default_applied)
