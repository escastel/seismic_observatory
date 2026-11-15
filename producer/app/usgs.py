"""Every HTTP request to USGS goes through here (spec 003, research R1).

fetch() never raises because of the source: it returns a FetchResult that maps
one to one onto a row of core.extraction (outcome, HTTP status, attempts,
duration, body and error detail).

Retries: timeouts, connection errors, 429 and 5xx, up to max_attempts requests,
waiting 1, 2, 4 ... seconds or Retry-After when it is longer. A Retry-After
above LONG_RETRY_AFTER_SECONDS is not waited for inside the call: the result
carries retry_after_seconds so the caller does not ask again before then.
Other 4xx answers (400 "exceeds search limit" included) are not retried.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Literal

import requests

from common.settings import UsgsSettings

Outcome = Literal["ok", "not_modified", "http_error", "timeout", "invalid_json", "invalid_structure"]
Expect = Literal["collection", "count"]

LONG_RETRY_AFTER_SECONDS = 120
DETAIL_LIMIT = 500


@dataclass(frozen=True)
class FetchResult:
    url: str                          # final URL, query string included
    requested_at: datetime            # start of the first request (UTC)
    outcome: Outcome
    http_status: int | None           # status of the last response, None without response
    attempt_count: int
    duration_ms: int                  # all attempts and waits
    body: bytes | None                # last response body (None for 304 and network errors)
    payload: Any | None               # parsed JSON when outcome is ok
    error_detail: str | None
    last_modified: str | None         # Last-Modified header of a 200
    retry_after_seconds: float | None = None


def _retry_after(value: str | None) -> float | None:
    """Retry-After as seconds: an integer or an HTTP date."""
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        moment = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return max(0.0, (moment - datetime.now(timezone.utc)).total_seconds())


def _structure_problem(payload: Any, expect: Expect) -> str | None:
    if expect == "count":
        if not isinstance(payload, dict) or not isinstance(payload.get("count"), int):
            return "count response without an integer 'count'"
        return None
    if not isinstance(payload, dict):
        return f"expected a GeoJSON FeatureCollection object, got {type(payload).__name__}"
    if payload.get("type") != "FeatureCollection":
        return f"expected type FeatureCollection, got {payload.get('type')!r}"
    if not isinstance(payload.get("features"), list):
        return "FeatureCollection without a 'features' list"
    return None


def _reject_constant(name: str) -> None:
    # NaN and Infinity are accepted by Python's json but are not JSON (RFC 8259).
    raise ValueError(f"{name} is not valid JSON")


def _excerpt(body: bytes) -> str:
    return body.decode("utf-8", errors="replace").strip()[:DETAIL_LIMIT]


def fetch(
    url: str,
    params: Mapping[str, Any] | None = None,
    *,
    settings: UsgsSettings,
    if_modified_since: str | None = None,
    expect: Expect = "collection",
    sleep: Callable[[float], object] = time.sleep,
    session: requests.Session | None = None,
) -> FetchResult:
    """GET url once, retrying transient failures; classify the result."""
    final_url = requests.Request("GET", url, params=dict(params or {})).prepare().url or url
    headers = {"User-Agent": settings.user_agent, "Accept": "application/json"}
    if if_modified_since:
        headers["If-Modified-Since"] = if_modified_since
    client = session or requests

    requested_at = datetime.now(timezone.utc)
    started = time.monotonic()

    def done(outcome: Outcome, attempts: int, **fields: Any) -> FetchResult:
        return FetchResult(
            url=final_url,
            requested_at=requested_at,
            outcome=outcome,
            attempt_count=attempts,
            duration_ms=int((time.monotonic() - started) * 1000),
            http_status=fields.get("http_status"),
            body=fields.get("body"),
            payload=fields.get("payload"),
            error_detail=fields.get("error_detail"),
            last_modified=fields.get("last_modified"),
            retry_after_seconds=fields.get("retry_after_seconds"),
        )

    attempt = 0
    while True:
        attempt += 1
        retry_after: float | None = None
        try:
            response = client.get(url, params=params, headers=headers, timeout=settings.timeout_seconds)
        except requests.Timeout as exc:
            last = {"error_detail": f"timeout after {settings.timeout_seconds} s: {exc}"[:DETAIL_LIMIT]}
            outcome: Outcome = "timeout"
        except requests.RequestException as exc:
            last = {"error_detail": f"connection error: {exc}"[:DETAIL_LIMIT]}
            outcome = "timeout"
        else:
            status = response.status_code
            body = response.content
            if status == 304:
                return done("not_modified", attempt, http_status=304)
            if status == 200:
                try:
                    payload = json.loads(body.decode("utf-8"), parse_constant=_reject_constant)
                except (UnicodeDecodeError, ValueError) as exc:
                    return done("invalid_json", attempt, http_status=200, body=body,
                                error_detail=f"response is not JSON: {exc}"[:DETAIL_LIMIT])
                problem = _structure_problem(payload, expect)
                if problem:
                    return done("invalid_structure", attempt, http_status=200, body=body, error_detail=problem)
                return done("ok", attempt, http_status=200, body=body, payload=payload,
                            last_modified=response.headers.get("Last-Modified"))
            detail = f"HTTP {status}: {_excerpt(body)}" if body else f"HTTP {status}"
            retry_after = _retry_after(response.headers.get("Retry-After"))
            if retry_after is not None:
                detail = f"{detail} (Retry-After {retry_after:.0f} s)"
            last = {"http_status": status, "body": body, "error_detail": detail[:DETAIL_LIMIT]}
            outcome = "http_error"
            if status != 429 and status < 500:
                return done(outcome, attempt, **last)  # 4xx other than 429: retrying will not help
            if retry_after is not None and retry_after > LONG_RETRY_AFTER_SECONDS:
                return done(outcome, attempt, retry_after_seconds=retry_after, **last)

        if attempt >= settings.max_attempts:
            return done(outcome, attempt, retry_after_seconds=retry_after, **last)
        sleep(max(float(2 ** (attempt - 1)), retry_after or 0.0))


async def fetch_async(url: str, params: Mapping[str, Any] | None = None, **kwargs: Any) -> FetchResult:
    """fetch() in a worker thread, so the asyncio loop keeps running."""
    return await asyncio.to_thread(fetch, url, params, **kwargs)
