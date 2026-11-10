"""FastAPI application for seismic event queries."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator, Literal

import asyncpg
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import ApiConfig
from .db import database_error
from .queries import count_events, country_stats, fetch_events, timeline_stats
from .schemas import (
    CountryStatsResponse,
    EventFilters,
    EventResponse,
    EventsResponse,
    GeoJSONFeatureCollection,
    TimelineResponse,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)
config = ApiConfig()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        app.state.db_pool = await asyncpg.create_pool(config.database_dsn, min_size=1, max_size=10)
    except (OSError, asyncpg.PostgresError) as exc:
        logger.error("Database pool initialization failed: %s", exc)
        app.state.db_pool = None
    yield
    if app.state.db_pool is not None:
        await app.state.db_pool.close()


app = FastAPI(
    title="Observatorio Sísmico",
    openapi_url=f"{config.api_prefix}/openapi.json",
    lifespan=lifespan,
)

origins = [origin.strip() for origin in config.cors_origins.split(",") if origin.strip()]
allow_all_origins = origins == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=not allow_all_origins,
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
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def event_filters(
    country: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    min_magnitude: float | None = Query(default=None),
    max_magnitude: float | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
) -> EventFilters:
    return filters_from_query(country, date_from, date_to, min_magnitude, max_magnitude, limit, offset)


@app.get(f"{config.api_prefix}/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


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
                "properties": item.model_dump(mode="json", exclude={"longitude", "latitude", "depth_km", "id"}),
            })
        return GeoJSONFeatureCollection(features=features)
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
    return TimelineResponse(
        bucket=bucket,
        items=[{"period": row["period"].isoformat(), "count": row["count"]} for row in rows],
    )
