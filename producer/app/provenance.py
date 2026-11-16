"""Writes of the ingestion provenance into core (spec 003, data-model.md §2–§4).

Every function takes an asyncpg connection whose search_path is core and runs
inside the caller's transaction when there is one. The tables belong to the
data model of spec 002; nothing here creates or alters them.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import asyncpg

from .classify import Excluded, millis_to_utc
from .usgs import FetchResult

SOURCES = ("usgs_feed", "usgs_catalog")
PURPOSES = ("live", "historical_load", "gap_recovery", "replay_selection")


@dataclass(frozen=True)
class Counts:
    """Split of the items of one response (FR-003). None means "not applicable"."""

    record: int | None = None
    earthquake: int | None = None
    excluded: int | None = None
    published: int | None = None


INSERT_EXTRACTION = """
INSERT INTO extraction (
    source, purpose, request_url, request_params, window_start, window_end,
    requested_at, duration_ms, attempt_count, http_status, outcome, error_detail,
    source_generated_at, record_count, earthquake_count, excluded_count, published_count,
    content_sha256
)
VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
RETURNING extraction_id
"""


def source_generated_at(result: FetchResult) -> datetime | None:
    """metadata.generated of a valid collection, as UTC."""
    if result.outcome != "ok" or not isinstance(result.payload, dict):
        return None
    metadata = result.payload.get("metadata")
    return millis_to_utc(metadata.get("generated")) if isinstance(metadata, dict) else None


async def record_extraction(
    conn: asyncpg.Connection,
    result: FetchResult,
    *,
    source: str,
    purpose: str,
    counts: Counts | None = None,
    fingerprint: str | None = None,
    request_params: Mapping[str, Any] | None = None,
    window: tuple[datetime, datetime] | None = None,
    extra_detail: str | None = None,
) -> int:
    """One row per request to USGS, successful or not (FR-001). Returns extraction_id."""
    if source not in SOURCES:
        raise ValueError(f"unknown source {source!r}")
    if purpose not in PURPOSES:
        raise ValueError(f"unknown purpose {purpose!r}")
    counts = counts or Counts()
    detail = "; ".join(part for part in (result.error_detail, extra_detail) if part) or None
    return await conn.fetchval(
        INSERT_EXTRACTION,
        source,
        purpose,
        result.url,
        json.dumps(dict(request_params), sort_keys=True) if request_params is not None else None,
        window[0] if window else None,
        window[1] if window else None,
        result.requested_at,
        result.duration_ms,
        result.attempt_count,
        result.http_status,
        result.outcome,
        detail,
        source_generated_at(result),
        counts.record,
        counts.earthquake,
        counts.excluded,
        counts.published,
        fingerprint,
    )


async def set_published_count(conn: asyncpg.Connection, extraction_id: int, published: int) -> None:
    await conn.execute("UPDATE extraction SET published_count = $2 WHERE extraction_id = $1", extraction_id, published)


UPSERT_PAYLOAD = """
INSERT INTO raw_payload (content_sha256, encoding, body, file_path, byte_size, first_seen_at, last_seen_at)
VALUES ($1, $2, $3, $4, $5, coalesce($6, now()), coalesce($6, now()))
ON CONFLICT (content_sha256) DO UPDATE
SET last_seen_at = greatest(raw_payload.last_seen_at, EXCLUDED.last_seen_at)
"""


async def store_body(conn: asyncpg.Connection, fingerprint: str, body: bytes, seen_at: datetime | None = None) -> None:
    """The response as received, gzip-compressed, once per fingerprint (FR-004, FR-005)."""
    await conn.execute(UPSERT_PAYLOAD, fingerprint, "gzip", gzip.compress(body), None, len(body), seen_at)


async def store_file(
    conn: asyncpg.Connection, fingerprint: str, relative_path: str, byte_size: int, seen_at: datetime | None = None
) -> None:
    """A catalog download kept as a file under data/ (FR-022): only fingerprint and path."""
    await conn.execute(UPSERT_PAYLOAD, fingerprint, "file", None, relative_path, byte_size, seen_at)


async def touch_payload(conn: asyncpg.Connection, fingerprint: str, seen_at: datetime | None = None) -> bool:
    """A 304 means the last content is still current: keep it from being purged."""
    status = await conn.execute(
        "UPDATE raw_payload SET last_seen_at = greatest(last_seen_at, coalesce($2, now())) WHERE content_sha256 = $1",
        fingerprint,
        seen_at,
    )
    return status.endswith(" 1")


async def payload_exists(conn: asyncpg.Connection, fingerprint: str) -> bool:
    return bool(await conn.fetchval("SELECT EXISTS (SELECT 1 FROM raw_payload WHERE content_sha256 = $1)", fingerprint))


INSERT_EXCLUSION = """
INSERT INTO excluded_event (event_id, updated_at, event_type, reason_code, extraction_id, payload)
VALUES ($1, $2, $3, $4, $5, $6::jsonb)
ON CONFLICT (event_id, updated_at) DO NOTHING
"""


async def record_exclusions(conn: asyncpg.Connection, excluded: Sequence[Excluded], extraction_id: int) -> int:
    """Non-earthquake versions, once per (event_id, updated_at) (FR-010). Returns rows inserted."""
    inserted = 0
    for entry in excluded:
        status = await conn.execute(
            INSERT_EXCLUSION,
            entry.item.event_id,
            entry.item.updated_at,
            entry.item.event_type,
            entry.reason_code,
            extraction_id,
            json.dumps(entry.item.feature, ensure_ascii=False),
        )
        inserted += int(status.endswith(" 1"))
    return inserted


LAST_SUCCESSFUL_FEED = """
SELECT max(requested_at) FROM extraction
WHERE source = 'usgs_feed' AND outcome IN ('ok', 'not_modified')
"""


async def last_successful_feed_request(conn: asyncpg.Connection) -> datetime | None:
    """last_ingestion of the API contract: last good request to the feed (FR-014)."""
    return await conn.fetchval(LAST_SUCCESSFUL_FEED)
