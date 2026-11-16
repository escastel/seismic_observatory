"""Synthetic replay cases (specs/005-historical-replay/contracts/synthetic-cases.md, research R10).

Fixed dates (2025-06-15 UTC), never relative to "now", so the expected outcome
is the same on every run. Kept free of database imports on purpose.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .runner import ReplayItem

ID_PREFIX = "synthetic-replay-"

EVENT_TIME = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)
U1 = datetime(2025, 6, 15, 12, 10, tzinfo=timezone.utc)
U2 = datetime(2025, 6, 15, 13, 30, tzinfo=timezone.utc)


def _ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def _feature(case: str, *, mag: float, updated: datetime, latitude: float = 10.0) -> dict[str, Any]:
    return {
        "type": "Feature",
        "id": f"{ID_PREFIX}{case}",
        "geometry": {"type": "Point", "coordinates": [-70.0, latitude, 10.0]},
        "properties": {
            "mag": mag,
            "time": _ms(EVENT_TIME),
            "updated": _ms(updated),
            "place": f"Synthetic replay case {case}",
            "magType": "ml",
            "type": "earthquake",
        },
    }


def synthetic_items() -> list[ReplayItem]:
    """The seven synthetic items, in the fixed order of the contract."""
    first = _feature("first", mag=4.1, updated=U1)
    return [
        ReplayItem(first, "first"),
        ReplayItem(dict(first), "first_duplicate"),
        ReplayItem(_feature("revised", mag=4.1, updated=U1), "revised_v1"),
        ReplayItem(_feature("revised", mag=4.4, updated=U2), "revised_v2"),
        ReplayItem(_feature("stale", mag=4.1, updated=U2), "stale_new"),
        ReplayItem(_feature("stale", mag=4.1, updated=U1), "stale_old"),
        ReplayItem(_feature("bad-coordinates", mag=4.1, updated=U1, latitude=145.0), "bad_coordinates"),
    ]
