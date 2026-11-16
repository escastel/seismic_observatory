"""FastAPI application of the observatory: read-only queries following CONTRATO-API.md.

Routes: GET /api/eventos, GET /api/estadisticas and GET /api/salud. It never queries USGS
and has no write or administration route.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from common import settings
from common.logging import configure

from . import db
from .db import DATABASE_ERRORS, DatabaseUnavailable, guard, pool_for
from .filters import ParameterError, QueryFilters, build_where, parse_filters
from .queries import (
    count_null_magnitude,
    count_total,
    fetch_page,
    last_ingestion,
    last_replayed_at,
    quarantine_counts,
    snapshot,
)
from .serialize import JsonResponse, feature_from_row, to_ms
from .stats import (
    compare,
    comparison_counts,
    counts_by_country,
    depth_distribution,
    hourly_counts,
    magnitude_distribution,
)

configure("api")
logger = logging.getLogger(__name__)
# The tunnel (ngrok) is the optional compose service "tunnel", never part of this process.
config = settings.api()

REPLAY_LABEL = "REPRODUCCIÓN"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.max_features = config.max_features
    connecting = db.start(app, config.database)
    try:
        yield
    finally:
        await db.stop(app, connecting)


app = FastAPI(
    title="Observatorio Sísmico",
    openapi_url=f"{config.api_prefix}/openapi.json",
    docs_url=None,
    redoc_url=None,
    default_response_class=JsonResponse,
    lifespan=lifespan,
)
# State used until the lifespan (or a test harness) sets it.
app.state.pools = {mode: None for mode in db.MODES}
app.state.max_features = config.max_features

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=False,  # public read-only API: no cookies
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type", "ngrok-skip-browser-warning"],
    max_age=600,
)


# --- errors: always explicit, always JSON -------------------------------------------------


@app.exception_handler(ParameterError)
async def parameter_error_handler(request: Request, exc: ParameterError) -> Response:
    return JsonResponse(
        {"error": "invalid_parameters", "detail": [{"param": exc.param, "message": exc.message}]},
        status_code=422,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> Response:
    detail = [
        {"param": str(error["loc"][-1]) if error.get("loc") else "request", "message": error["msg"]}
        for error in exc.errors()
    ]
    return JsonResponse({"error": "invalid_parameters", "detail": detail}, status_code=422)


@app.exception_handler(DatabaseUnavailable)
async def database_unavailable_handler(request: Request, exc: DatabaseUnavailable) -> Response:
    return JsonResponse({"error": "database_unavailable", "detail": str(exc)}, status_code=503)


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> Response:
    logger.exception("Unexpected error in %s", request.url.path)
    return JsonResponse(
        {"error": "internal_error", "detail": "Unexpected error; see the API log"}, status_code=500
    )


# --- shared parameters --------------------------------------------------------------------


def common_filters(
    mode: str = Query(default="live", description="live | replay"),
    start: datetime | None = Query(default=None, description="ISO 8601 with zone, inclusive"),
    end: datetime | None = Query(default=None, description="ISO 8601 with zone, exclusive"),
    min_mag: float | None = Query(default=None),
    country_id: str | None = Query(default=None),
    exclude_synthetic: bool = Query(default=False),
) -> QueryFilters:
    return parse_filters(mode, start, end, min_mag, country_id, exclude_synthetic)


def _ms_or_none(value: datetime | None) -> int | None:
    return to_ms(value) if value is not None else None


def _period(where: Any) -> dict[str, Any]:
    return {
        "start": _ms_or_none(where.period_start),
        "end": _ms_or_none(where.period_end),
        "default_applied": where.default_applied,
    }


# --- GET /api/eventos ---------------------------------------------------------------------


@app.get(f"{config.api_prefix}/eventos")
async def events(
    request: Request,
    filters: QueryFilters = Depends(common_filters),
    limit: int | None = Query(default=None, description="page size, 1 to the documented maximum"),
    offset: int = Query(default=0, ge=0),
) -> Response:
    max_features: int = request.app.state.max_features
    if limit is None:
        limit = max_features
    if not 1 <= limit <= max_features:
        raise ParameterError("limit", f"must be between 1 and {max_features}")

    replay = filters.mode == "replay"
    now = datetime.now(timezone.utc)
    where = build_where(filters, now)
    where_all_magnitudes = build_where(filters, now, with_min_mag=False)

    with guard():
        pool = pool_for(request, filters.mode)
        async with snapshot(pool) as conn:
            rows = await fetch_page(conn, where, limit, offset, replay=replay)
            total = await count_total(conn, where)
            null_magnitude = await count_null_magnitude(conn, where_all_magnitudes)
            quarantined = await quarantine_counts(conn)
            ingestion = await last_ingestion(conn)
            replayed = await last_replayed_at(conn) if replay else None

    features = [feature_from_row(row, replay) for row in rows]
    count = len(features)
    truncated = offset + count < total
    metadata: dict[str, Any] = {
        "generated": to_ms(now),
        "last_ingestion": _ms_or_none(ingestion),
        "mode": filters.mode,
        "count": count,
        "total": total,
        "truncated": truncated,
        "limit": limit,
        "offset": offset,
        "next_offset": offset + count if truncated else None,
        "period": _period(where),
        "null_magnitude": {"count": null_magnitude, "excluded": filters.min_mag is not None},
        "quarantined": quarantined,
    }
    if replay:
        metadata["label"] = REPLAY_LABEL
        metadata["last_replayed_at"] = _ms_or_none(replayed)
    logger.info("API metrics endpoint=eventos mode=%s returned=%d total=%d", filters.mode, count, total)
    return JsonResponse({"type": "FeatureCollection", "metadata": metadata, "features": features})


# --- GET /api/salud -----------------------------------------------------------------------


@app.get(f"{config.api_prefix}/salud")
async def health(request: Request) -> Response:
    """Always answers 200: «degraded» when a database pool cannot answer. No credentials."""
    states: dict[str, str] = {}
    working_pool = None
    for mode, key in (("live", "database"), ("replay", "replay_database")):
        pool = request.app.state.pools.get(mode)
        try:
            if pool is None:
                raise DatabaseUnavailable(f"The {mode} database pool is not open")
            await pool.fetchval("SELECT 1")
            states[key] = "ok"
            working_pool = working_pool or pool
        except (DatabaseUnavailable, *DATABASE_ERRORS) as exc:
            logger.warning("Health check: %s pool failed: %s", mode, exc)
            states[key] = "unavailable"

    ingestion = None
    if working_pool is not None and states["database"] == "ok":
        try:
            ingestion = await last_ingestion(working_pool)
        except DATABASE_ERRORS as exc:
            logger.warning("Health check could not read the last ingestion: %s", exc)
            states["database"] = "unavailable"

    status = "ok" if all(value == "ok" for value in states.values()) else "degraded"
    return JsonResponse(
        {
            "status": status,
            **states,
            "generated": to_ms(datetime.now(timezone.utc)),
            "last_ingestion": _ms_or_none(ingestion),
        }
    )


# --- GET /api/estadisticas ----------------------------------------------------------------


@app.get(f"{config.api_prefix}/estadisticas")
async def statistics(
    request: Request,
    filters: QueryFilters = Depends(common_filters),
    baseline_year: int = Query(default=2025, ge=1900, le=2100),
) -> Response:
    """Aggregations over the whole filtered set (never over a page), from the current state."""
    replay = filters.mode == "replay"
    now = datetime.now(timezone.utc)
    where = build_where(filters, now)

    with guard():
        pool = pool_for(request, filters.mode)
        async with snapshot(pool) as conn:
            total = await count_total(conn, where)
            period, hourly = await hourly_counts(conn, filters, now)
            by_country = await counts_by_country(conn, filters, now)
            magnitudes = await magnitude_distribution(conn, filters, now)
            depths = await depth_distribution(conn, filters, now)
            raw = await comparison_counts(conn, filters, now, baseline_year)
            ingestion = await last_ingestion(conn)
            replayed = await last_replayed_at(conn) if replay else None

    metadata: dict[str, Any] = {
        "generated": to_ms(now),
        "last_ingestion": _ms_or_none(ingestion),
        "mode": filters.mode,
    }
    if replay:
        metadata["label"] = REPLAY_LABEL
        metadata["last_replayed_at"] = _ms_or_none(replayed)
    comparison = {
        "recent": raw["recent"],
        **compare(
            raw["recent"]["count"], raw["baseline_events"], raw["year"], anchor_is_data=raw["anchor_is_data"]
        ),
    }
    logger.info("API metrics endpoint=estadisticas mode=%s total=%d", filters.mode, total)
    return JsonResponse(
        {
            "mode": filters.mode,
            "metadata": metadata,
            "scope": "complete",
            "map_truncated": total > request.app.state.max_features,
            "period": period,
            "filters": {
                "min_mag": filters.min_mag,
                "country_id": filters.country_id,
                "exclude_synthetic": filters.exclude_synthetic,
            },
            "unit": "events",
            "total": total,
            "hourly": {"window": "1 hour UTC, end excluded", "items": hourly},
            "by_country": {"items": by_country},
            "magnitude_distribution": magnitudes,
            "depth_distribution": depths,
            "comparison": comparison,
        }
    )
