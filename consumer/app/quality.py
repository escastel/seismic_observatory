"""Quality WAF for incoming USGS events."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


MIN_MAGNITUDE = 0.0
MAX_MAGNITUDE = 10.0
FUTURE_TIMESTAMP_TOLERANCE = timedelta(seconds=300)
RAW_EVENT_MAX_AGE = timedelta(days=7)
# Topic of the live feed: only its events must be recent (RAW_EVENT_MAX_AGE).
LIVE_TOPIC = "earthquakes.live"


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
    mag_type: str | None
    longitude: float
    latitude: float
    depth_km: float | None
    place: str
    original_payload: Any


def _failure(dimension: str, code: str, detail: str) -> QualityFailure:
    return QualityFailure(dimension, code, detail)


def validate_event(
    payload: Any,
    seen_ids: set[str] | None = None,
    source_topic: str = LIVE_TOPIC,
    now: datetime | None = None,
    live_topic: str = LIVE_TOPIC,
) -> tuple[ValidatedEvent | None, list[QualityFailure]]:
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

    reference_time = now or datetime.now(timezone.utc)
    if event_time is not None:
        if event_time > reference_time + FUTURE_TIMESTAMP_TOLERANCE:
            failures.append(
                _failure(
                    "Frescura",
                    "future_timestamp",
                    "event time cannot be more than 300 seconds in the future",
                )
            )
        elif source_topic == live_topic and reference_time - event_time > RAW_EVENT_MAX_AGE:
            failures.append(
                _failure(
                    "Frescura",
                    "event_too_old",
                    "raw events cannot be older than 7 days",
                )
            )

    try:
        magnitude = float(magnitude_raw)
    except (TypeError, ValueError):
        failures.append(_failure("Validez", "magnitude_not_numeric", "mag must be numeric"))
        magnitude = 0.0
    if not math.isfinite(magnitude):
        failures.append(_failure("Exactitud", "magnitude_not_finite", "mag must be finite"))
    elif not MIN_MAGNITUDE <= magnitude <= MAX_MAGNITUDE:
        failures.append(
            _failure(
                "Validez",
                "magnitude_out_of_range",
                f"mag must be between {MIN_MAGNITUDE} and {MAX_MAGNITUDE}",
            )
        )

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
    if seen_ids is not None and event_id.strip() in seen_ids:
        failures.append(_failure("Unicidad", "duplicate_id", "id was already observed"))
    if failures:
        return None, failures
    return (
        ValidatedEvent(
            external_id=event_id.strip(),
            updated=updated,
            event_time=event_time,
            magnitude=magnitude,
            mag_type=str((payload.get("properties") or {}).get("magType") or payload.get("magType") or "") or None,
            longitude=longitude,
            latitude=latitude,
            depth_km=depth_km,
            place=str(payload.get("place") or ""),
            original_payload=payload,
        ),
        [],
    )
