"""Message of the earthquakes.replay topic (specs/005-historical-replay/contracts/replay-message.md).

time and updated come from the feature properties and are never modified
(constitution, principle VI). Kept free of database imports on purpose.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

SOURCE_CATALOG = "usgs_catalog"
MODE_REPLAY = "replay"


def format_utc(moment: datetime) -> str:
    """ISO 8601 in UTC with a trailing Z (a naive datetime is taken as UTC)."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_replay_message(
    feature: dict[str, Any],
    *,
    extraction_id: int | None,
    replayed_at: datetime,
    run: str,
    synthetic_case: str | None = None,
) -> dict[str, Any]:
    """Message value of the replay topic; the consumer reads the top-level copies."""
    properties = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    stamp = format_utc(replayed_at)
    message: dict[str, Any] = {
        "id": feature.get("id"),
        "updated": properties.get("updated"),
        "time": properties.get("time"),
        "mag": properties.get("mag"),
        "place": properties.get("place"),
        "geometry": feature.get("geometry"),
        "properties": properties,
        "original_event": feature,
        "source": SOURCE_CATALOG,
        "ingested_at": stamp,
        "mode": MODE_REPLAY,
        "extraction_id": extraction_id,
        "replayed_at": stamp,
        "replay_run": run,
    }
    if synthetic_case is not None:
        message["synthetic"] = True
        message["synthetic_case"] = synthetic_case
    return message


def encode(message: dict[str, Any]) -> bytes:
    return json.dumps(message, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
