"""FastAPI application for seismic event queries."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator, Literal

import asyncpg
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from common import settings
from common.logging import configure

from . import db
from .db import database_error
from .queries import (
    count_events,
    country_stats,
    daily_average_2025,
    depth_stats,
    fetch_events,
    magnitude_stats,
    missing_magnitude,
    timeline_stats,
)
from .schemas import (
    CountryStatsResponse,
    EventFilters,
    EventResponse,
    EventsResponse,
    GeoJSONFeatureCollection,
    TimelineResponse,
)

configure("api")
logger = logging.getLogger(__name__)
# The tunnel (ngrok) is the optional compose service "tunnel", never part of this process.
config = settings.api()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    connecting = db.start(app, config.database)
    try:
        yield
    finally:
        await db.stop(app, connecting)


app = FastAPI(
    title="Observatorio Sísmico",
    openapi_url=f"{config.api_prefix}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type", "ngrok-skip-browser-warning"],
)


def get_pool(request: Request) -> asyncpg.Pool:
    pool = request.app.state.db_pool
    if pool is None:
        raise database_error(RuntimeError("Database pool is unavailable"))
    return pool


def filters_from_query(
    country: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    min_magnitude: float | None,
    max_magnitude: float | None,
    limit: int = 1000,
    offset: int = 0,
    end_exclusive: bool = False,
) -> EventFilters:
    try:
        return EventFilters(
            country=country,
            date_from=date_from,
            date_to=date_to,
            min_magnitude=min_magnitude,
            max_magnitude=max_magnitude,
            limit=limit,
            offset=offset,
            end_exclusive=end_exclusive,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def event_filters(
    request: Request,
    country: str | None = Query(default=None),
    country_id: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    min_magnitude: float | None = Query(default=None),
    max_magnitude: float | None = Query(default=None),
    min_mag: float | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
) -> EventFilters:
    if start is None and date_from is None and request.url.path.endswith("/eventos"):
        start = datetime.now(timezone.utc) - timedelta(days=1)
    return filters_from_query(
        country,
        start or date_from,
        end or date_to,
        min_mag if min_mag is not None else min_magnitude,
        max_magnitude,
        limit,
        offset,
        end_exclusive=end is not None,
    ).model_copy(update={"country_id": country_id})


LAST_INGESTION_SQL = "SELECT MAX(ingested_at) FROM event_current"


@app.get(f"{config.api_prefix}/health")
async def health(request: Request) -> dict[str, str | int | None]:
    """Always answers: «degraded» when the database is not reachable. Never shows credentials."""
    pool = request.app.state.db_pool
    last_ingestion = None
    status = "degraded"
    if pool is not None:
        try:
            last_ingestion = await pool.fetchval(LAST_INGESTION_SQL)
            status = "ok"
        except (OSError, asyncpg.PostgresError, asyncpg.InterfaceError) as exc:
            logger.warning("Health check could not query the database: %s", exc)
    return {
        "status": status,
        "last_ingestion": last_ingestion.isoformat() if last_ingestion else None,
    }


@app.get(f"{config.api_prefix}/salud")
async def service_health(request: Request) -> dict[str, str | int | None]:
    return await health(request)


@app.get(f"{config.api_prefix}/eventos")
async def events(
    request: Request,
    filters: EventFilters = Depends(event_filters),
    format: Literal["json", "geojson"] = Query(default="json"),
) -> EventsResponse | GeoJSONFeatureCollection:
    pool = get_pool(request)
    try:
        rows = await fetch_events(pool, filters)
        total = await count_events(pool, filters)
    except (OSError, asyncpg.PostgresError) as exc:
        logger.error("Event query failed: %s", exc)
        raise database_error(exc) from exc

    items = [EventResponse.model_validate(dict(row)) for row in rows]
    logger.info(
        "API metrics endpoint=eventos returned=%d total=%d limit=%d offset=%d",
        len(items), total, filters.limit, filters.offset,
    )
    if format == "geojson" or request.headers.get("accept") == "application/geo+json":
        features = []
        for item in items:
            coordinates = [item.longitude, item.latitude]
            if item.depth_km is not None:
                coordinates.append(item.depth_km)
            features.append({
                "type": "Feature",
                "id": item.id,
                "geometry": {"type": "Point", "coordinates": coordinates},
                "properties": item.model_dump(
                    mode="json",
                    by_alias=True,
                    exclude={"longitude", "latitude", "depth_km", "id"},
                ),
            })
        last_ingestion = await pool.fetchval(LAST_INGESTION_SQL)
        return GeoJSONFeatureCollection(
            metadata={
                "generated": int(datetime.now(timezone.utc).timestamp() * 1000),
                "last_ingestion": int(last_ingestion.timestamp() * 1000) if last_ingestion else None,
                "mode": "live",
                "count": len(features),
                "total": total,
                "truncated": filters.offset + len(features) < total,
            },
            features=features,
        )
    return EventsResponse(items=items, count=total, limit=filters.limit, offset=filters.offset)


@app.get(f"{config.api_prefix}/estadisticas/paises")
async def countries(
    request: Request,
    filters: EventFilters = Depends(event_filters),
) -> CountryStatsResponse:
    pool = get_pool(request)
    try:
        rows = await country_stats(pool, filters)
    except (OSError, asyncpg.PostgresError) as exc:
        raise database_error(exc) from exc
    logger.info("API metrics endpoint=estadisticas/paises returned=%d", len(rows))
    return CountryStatsResponse(items=[dict(row) for row in rows])


@app.get(f"{config.api_prefix}/estadisticas/timeline")
async def timeline(
    request: Request,
    bucket: Literal["day", "week", "month"] = Query(default="day"),
    filters: EventFilters = Depends(event_filters),
) -> TimelineResponse:
    pool = get_pool(request)
    try:
        rows = await timeline_stats(pool, filters, bucket)
    except (OSError, asyncpg.PostgresError) as exc:
        raise database_error(exc) from exc
    logger.info("API metrics endpoint=estadisticas/timeline bucket=%s returned=%d", bucket, len(rows))
    return TimelineResponse(
        bucket=bucket,
        items=[{"period": row["period"].isoformat(), "count": row["count"]} for row in rows],
    )


@app.get(f"{config.api_prefix}/estadisticas")
async def statistics(
    request: Request,
    filters: EventFilters = Depends(event_filters),
) -> dict[str, object]:
    pool = get_pool(request)
    try:
        countries_rows = await country_stats(pool, filters)
        timeline_rows = await timeline_stats(pool, filters, "day")
        magnitude_rows = await magnitude_stats(pool, filters)
        depth_rows = await depth_stats(pool, filters)
        historical_average = await daily_average_2025(pool, filters)
        missing_magnitude_count = await missing_magnitude(pool, filters)
    except (OSError, asyncpg.PostgresError) as exc:
        raise database_error(exc) from exc
    return {
        "filters": filters.model_dump(mode="json"),
        "unit": "events",
        "countries": [dict(row) for row in countries_rows],
        "timeline": [{"period": row["period"].isoformat(), "count": row["count"]} for row in timeline_rows],
        "magnitude_distribution": [dict(row) for row in magnitude_rows],
        "depth_distribution": [dict(row) for row in depth_rows],
        "daily_average_2025": historical_average,
        "missing_magnitude": missing_magnitude_count,
    }
