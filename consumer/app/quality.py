"""Quality WAF for incoming USGS events."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class QualityFailure:
    dimension: str
    reason_code: str
    reason_detail: str


@dataclass(frozen=True)
class ValidatedEvent:
    external_id: str
    updated: datetime
    event_time: datetime
    magnitude: float
    longitude: float
    latitude: float
    depth_km: float | None
    place: str


def _failure(dimension: str, code: str, detail: str) -> QualityFailure:
    return QualityFailure(dimension, code, detail)


def validate_event(payload: Any) -> tuple[ValidatedEvent | None, list[QualityFailure]]:
    if not isinstance(payload, dict):
        return None, [_failure("Consistencia", "event_not_object", "Event must be a JSON object")]

    failures: list[QualityFailure] = []
    event_id = payload.get("id")
    updated_raw = payload.get("updated")
    event_time_raw = payload.get("time")
    if event_id is None or updated_raw is None or event_time_raw is None:
        failures.append(_failure("Completitud", "required_field_null", "id, updated and time are required"))

    geometry = payload.get("geometry")
    coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if coordinates is None:
        failures.append(_failure("Completitud", "coordinates_null", "geometry.coordinates must not be null"))
    elif not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
        failures.append(_failure("Validez", "coordinates_missing", "geometry.coordinates must contain longitude and latitude"))

    magnitude_raw = payload.get("mag")
    if magnitude_raw is None:
        failures.append(_failure("Completitud", "magnitude_null", "mag must not be null"))

    if failures:
        return None, failures

    if not isinstance(event_id, str) or not event_id.strip():
        failures.append(_failure("Consistencia", "id_invalid_type", "id must be a non-empty string"))

    try:
        updated = datetime.fromtimestamp(float(updated_raw) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        failures.append(_failure("Oportunidad", "updated_invalid", "updated must be a Unix timestamp in milliseconds"))
        updated = None

    try:
        event_time = datetime.fromtimestamp(float(event_time_raw) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        failures.append(_failure("Consistencia", "time_invalid", "time must be a Unix timestamp in milliseconds"))
        event_time = None

    try:
        magnitude = float(magnitude_raw)
    except (TypeError, ValueError):
        failures.append(_failure("Validez", "magnitude_not_numeric", "mag must be numeric"))
        magnitude = 0.0
    if not math.isfinite(magnitude):
        failures.append(_failure("Exactitud", "magnitude_not_finite", "mag must be finite"))

    try:
        longitude = float(coordinates[0])
        latitude = float(coordinates[1])
    except (TypeError, ValueError):
        failures.append(_failure("Validez", "coordinates_not_numeric", "coordinates must be numeric"))
        longitude = latitude = 0.0
    if not math.isfinite(longitude) or not math.isfinite(latitude):
        failures.append(_failure("Validez", "coordinates_not_finite", "coordinates must be finite"))
    elif not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        failures.append(_failure("Validez", "coordinates_out_of_range", "longitude/latitude are outside accepted ranges"))

    depth_km: float | None = None
    if len(coordinates) > 2 and coordinates[2] is not None:
        try:
            depth_km = float(coordinates[2])
        except (TypeError, ValueError):
            failures.append(_failure("Exactitud", "depth_not_numeric", "depth must be numeric when present"))
        else:
            if not math.isfinite(depth_km):
                failures.append(_failure("Exactitud", "depth_not_finite", "depth must be finite"))

    if failures or updated is None or event_time is None:
        return None, failures
    return (
        ValidatedEvent(
            external_id=event_id.strip(),
            updated=updated,
            event_time=event_time,
            magnitude=magnitude,
            longitude=longitude,
            latitude=latitude,
            depth_km=depth_km,
            place=str(payload.get("place") or ""),
        ),
        [],
    )
