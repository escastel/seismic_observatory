"""Row to GeoJSON Feature projection and the JSON response class of the query API."""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from fastapi.responses import JSONResponse

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
SYNTHETIC_PREFIX = "synthetic-"


def to_ms(dt: datetime | None) -> int | None:
    """Unix milliseconds as an exact integer; valid before 1970 on every platform."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt - EPOCH) // timedelta(milliseconds=1)


def finite_or_none(x: Any) -> float | None:
    """NaN, infinity and absent values become None (JSON has no representation for them)."""
    if x is None:
        return None
    try:
        value = float(x)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def feature_from_row(row: Mapping[str, Any], replay: bool) -> dict[str, Any]:
    """Build the Feature of data-model.md from a row of event_current joined with dim_country."""
    event_id = row["id"]
    properties: dict[str, Any] = {
        "mag": finite_or_none(row["mag"]),
        "magType": row["mag_type"],
        "place": row["place"],
        "time": to_ms(row["time"]),
        "updated": to_ms(row["updated"]),
        "country_id": row["country_id"],
        "country_name": row["country_name"],
        "continent": row["continent"],
        "subregion": row["subregion"],
    }
    if replay:
        properties["replayed_at"] = to_ms(row["replayed_at"])
        properties["synthetic"] = bool(row["is_synthetic"]) or str(event_id).startswith(SYNTHETIC_PREFIX)
    return {
        "type": "Feature",
        "id": event_id,
        "geometry": {
            "type": "Point",
            "coordinates": [
                finite_or_none(row["longitude"]),
                finite_or_none(row["latitude"]),
                finite_or_none(row["depth_km"]),
            ],
        },
        "properties": properties,
    }


class JsonResponse(JSONResponse):
    """Compact UTF-8 JSON that refuses NaN and infinity instead of emitting invalid JSON."""

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
