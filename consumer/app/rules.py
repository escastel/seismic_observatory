"""Quality rules of the consumer: one catalog, one evaluation per message.

Source of truth for specs/004-consumer-quality/contracts/rules-catalog.md (a test
keeps both in step). Four effects, in order of gravity: quarantine (the message
cannot be treated), exclusion (understood, but not an earthquake), flag (stored
and signalled in quality_flags) and transformation (text number -> number,
milliseconds -> UTC, always flagged). A missing value is stored as NULL, never
as zero (principle III).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

MIN_MAGNITUDE = -2.0
MAX_MAGNITUDE = 10.0
MAX_DEPTH_KM = 800.0
FUTURE_TOLERANCE = timedelta(minutes=5)


@dataclass(frozen=True)
class Rule:
    code: str
    dimension: str
    effect: str  # quarantine | exclusion | flag
    description: str


CATALOG: tuple[Rule, ...] = (
    Rule("malformed_json", "Validez", "quarantine", "The message is not JSON (or contains NaN/Infinity)"),
    Rule("not_an_object", "Consistencia", "quarantine", "The JSON is not an object"),
    Rule("missing_id", "Completitud", "quarantine", "id is missing"),
    Rule("invalid_id", "Consistencia", "quarantine", "id is not a non-empty string"),
    Rule("missing_time", "Completitud", "quarantine", "time is missing"),
    Rule("invalid_time", "Validez", "quarantine", "time is not a Unix instant in milliseconds"),
    Rule("missing_updated", "Completitud", "quarantine", "updated is missing"),
    Rule("invalid_updated", "Validez", "quarantine", "updated is not a Unix instant in milliseconds"),
    Rule("geometry_missing", "Completitud", "quarantine", "geometry is missing"),
    Rule("geometry_not_point", "Validez", "quarantine", "geometry.type is not Point"),
    Rule("coordinates_missing", "Completitud", "quarantine", "coordinates lack longitude and latitude"),
    Rule("coordinates_not_numeric", "Validez", "quarantine", "longitude or latitude is not numeric"),
    Rule("coordinates_not_finite", "Validez", "quarantine", "longitude or latitude is NaN or infinite"),
    Rule("coordinates_out_of_range", "Validez", "quarantine", "longitude outside [-180, 180] or latitude outside [-90, 90]"),
    Rule("model_constraint_violation", "Consistencia", "quarantine", "The data model rejects the version (raised by the consumer, not evaluate)"),
    Rule("not_earthquake", "Consistencia", "exclusion", "properties.type is not earthquake"),
    Rule("missing_type", "Completitud", "exclusion", "properties.type is missing"),
    Rule("negative_depth", "Validez", "flag", "Depth below zero"),
    Rule("magnitude_out_of_range", "Validez", "flag", "Magnitude below -2 or above 10"),
    Rule("depth_out_of_range", "Validez", "flag", "Depth above 800 km"),
    Rule("future_time", "Actualidad", "flag", "Occurrence more than 5 minutes after reception"),
    Rule("updated_before_time", "Consistencia", "flag", "updated earlier than time"),
    Rule("magnitude_from_text", "Validez", "flag", "Magnitude arrived as numeric text and was converted"),
    Rule("depth_from_text", "Validez", "flag", "Depth arrived as numeric text and was converted"),
    Rule("magnitude_not_numeric", "Validez", "flag", "Magnitude arrived as non-numeric text; stored NULL"),
    Rule("depth_not_numeric", "Validez", "flag", "Depth arrived as non-numeric text; stored NULL"),
    Rule("extra_coordinates", "Validez", "flag", "More than three values in coordinates"),
    Rule("ambiguous_country", "Consistencia", "flag", "The point falls in several country entities (added by the consumer)"),
    Rule("synthetic", "—", "flag", "Test message damaged on purpose"),
)

_DETAIL = {rule.code: rule for rule in CATALOG}


@dataclass(frozen=True)
class ValidatedEvent:
    external_id: str
    updated: datetime
    event_time: datetime
    magnitude: float | None
    mag_type: str | None
    longitude: float
    latitude: float
    depth_km: float | None
    place: str | None


@dataclass(frozen=True)
class Accepted:
    event: ValidatedEvent
    flags: list[str]
    synthetic: bool
    original: dict
    produced_at: datetime | None


@dataclass(frozen=True)
class Exclusion:
    reason_code: str
    event_id: str
    updated_at: datetime
    event_type: str | None
    feature: dict
    synthetic: bool


@dataclass(frozen=True)
class Quarantine:
    reasons: list[str]
    detail: str
    payload: Any | None
    raw_text: str | None
    event_id: str | None
    synthetic: bool


def _reject_constant(name: str) -> None:
    raise ValueError(f"{name} is not valid JSON")


def _number(value: Any) -> float | None:
    """A JSON number as float; None when it is not one (booleans are not numbers)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _instant(value: Any) -> datetime | None:
    number = _number(value)
    if number is None or not math.isfinite(number):
        return None
    try:
        # Not fromtimestamp(): on Windows it raises OSError for instants before 1970.
        return EPOCH + timedelta(milliseconds=number)
    except (OverflowError, OSError, ValueError):
        return None


def _pick(message: dict, properties: dict, key: str) -> Any:
    """Top-level value of the flat message, else the one in properties."""
    value = message.get(key)
    return properties.get(key) if value is None else value


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _measure(value: Any, flag_prefix: str, flags: set[str]) -> float | None:
    """Magnitude or depth: null stays null; numeric text converts; the rest becomes null."""
    if value is None:
        return None
    number = _number(value)
    if number is not None:
        return number if math.isfinite(number) else _not_numeric(flag_prefix, flags)
    if isinstance(value, str):
        try:
            converted = float(value)
        except ValueError:
            return _not_numeric(flag_prefix, flags)
        if not math.isfinite(converted):
            return _not_numeric(flag_prefix, flags)
        flags.add(f"{flag_prefix}_from_text")
        return converted
    return _not_numeric(flag_prefix, flags)


def _not_numeric(prefix: str, flags: set[str]) -> None:
    flags.add(f"{prefix}_not_numeric")
    return None


def _describe(code: str) -> str:
    return f"{_DETAIL[code].dimension}: {code} ({_DETAIL[code].description})"


def _quarantine(codes: list[str], payload: Any, event_id: str | None, synthetic: bool) -> Quarantine:
    detail = "; ".join(_describe(code) for code in codes)
    return Quarantine(codes, detail, payload, None, event_id, synthetic)


def evaluate(raw: bytes, received_at: datetime) -> Accepted | Exclusion | Quarantine:
    """Apply every rule to one Kafka message; quarantine reasons are all collected."""
    try:
        # NaN and Infinity are not JSON (RFC 8259) and jsonb rejects them.
        decoded = json.loads(raw, parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError):
        text = bytes(raw).decode("utf-8", errors="replace")
        return Quarantine(
            ["malformed_json"], _describe("malformed_json"),
            None, text, None, False,
        )
    if not isinstance(decoded, dict):
        return _quarantine(["not_an_object"], decoded, None, False)

    synthetic = decoded.get("synthetic") is True
    properties = decoded.get("properties") if isinstance(decoded.get("properties"), dict) else {}
    reasons: list[str] = []

    event_id = decoded.get("id")
    if event_id is None:
        reasons.append("missing_id")
    elif not isinstance(event_id, str) or not event_id.strip():
        reasons.append("invalid_id")

    event_time = updated = None
    for key, missing, invalid in (("time", "missing_time", "invalid_time"), ("updated", "missing_updated", "invalid_updated")):
        value = _pick(decoded, properties, key)
        if value is None:
            reasons.append(missing)
        elif (instant := _instant(value)) is None:
            reasons.append(invalid)
        elif key == "time":
            event_time = instant
        else:
            updated = instant

    longitude = latitude = None
    depth_raw = None
    extra = False
    geometry = decoded.get("geometry")
    if geometry is None:
        reasons.append("geometry_missing")
    elif not isinstance(geometry, dict) or geometry.get("type") != "Point":
        reasons.append("geometry_not_point")
    else:
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) < 2 or coordinates[0] is None or coordinates[1] is None:
            reasons.append("coordinates_missing")
        else:
            lon, lat = _number(coordinates[0]), _number(coordinates[1])
            if lon is None or lat is None:
                reasons.append("coordinates_not_numeric")
            elif not math.isfinite(lon) or not math.isfinite(lat):
                reasons.append("coordinates_not_finite")
            elif not -180 <= lon <= 180 or not -90 <= lat <= 90:
                reasons.append("coordinates_out_of_range")
            else:
                longitude, latitude = lon, lat
                depth_raw = coordinates[2] if len(coordinates) > 2 else None
                extra = len(coordinates) > 3

    safe_id = event_id if isinstance(event_id, str) else None
    if reasons:
        return _quarantine(reasons, decoded, safe_id, synthetic)

    assert event_time is not None and updated is not None and longitude is not None and latitude is not None
    original = decoded["original_event"] if isinstance(decoded.get("original_event"), dict) else decoded

    event_type = properties.get("type")
    if event_type is None:
        return Exclusion("missing_type", event_id.strip(), updated, None, original, synthetic)
    if event_type != "earthquake":
        return Exclusion("not_earthquake", event_id.strip(), updated, str(event_type), original, synthetic)

    flags: set[str] = set()
    magnitude = _measure(_pick(decoded, properties, "mag"), "magnitude", flags)
    depth_km = _measure(depth_raw, "depth", flags)
    if magnitude is not None and not MIN_MAGNITUDE <= magnitude <= MAX_MAGNITUDE:
        flags.add("magnitude_out_of_range")
    if depth_km is not None:
        if depth_km < 0:
            flags.add("negative_depth")
        elif depth_km > MAX_DEPTH_KM:
            flags.add("depth_out_of_range")
    if event_time > received_at + FUTURE_TOLERANCE:
        flags.add("future_time")
    if updated < event_time:
        flags.add("updated_before_time")
    if extra:
        flags.add("extra_coordinates")
    if synthetic:
        flags.add("synthetic")

    event = ValidatedEvent(
        external_id=event_id.strip(),
        updated=updated,
        event_time=event_time,
        magnitude=magnitude,
        mag_type=_text(_pick(decoded, properties, "magType")),
        longitude=longitude,
        latitude=latitude,
        depth_km=depth_km,
        place=_text(_pick(decoded, properties, "place")),
    )
    produced = decoded.get("ingested_at")
    produced_at = None
    if isinstance(produced, str):
        try:
            produced_at = datetime.fromisoformat(produced)
        except ValueError:
            produced_at = None
        else:
            produced_at = produced_at if produced_at.tzinfo else produced_at.replace(tzinfo=timezone.utc)
    return Accepted(event, sorted(flags), synthetic, original, produced_at)
