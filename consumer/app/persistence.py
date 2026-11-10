"""Transactional PostgreSQL persistence for accepted and quarantined events."""

from __future__ import annotations

from typing import Any

import psycopg2
from psycopg2.extras import Json

from .quality import ValidatedEvent
from .spatial import Geography


def persist_event(
    dsn: str,
    event: ValidatedEvent,
    geography: Geography,
    source_topic: str,
) -> None:
    with psycopg2.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO dim_geografia
                    (country, continent, subregion, source_dataset, geometry_hash)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (country, continent, subregion, source_dataset, geometry_hash)
                DO UPDATE SET country = EXCLUDED.country
                RETURNING geografia_key
                """,
                (
                    geography.country,
                    geography.continent,
                    geography.subregion,
                    geography.source_dataset,
                    geography.geometry_hash,
                ),
            )
            geography_key = cursor.fetchone()[0]
            event_date = event.event_time.date()
            cursor.execute(
                """
                INSERT INTO dim_tiempo (event_date, year, month, day, week)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (event_date)
                DO UPDATE SET event_date = EXCLUDED.event_date
                RETURNING tiempo_key
                """,
                (event_date, event_date.year, event_date.month, event_date.day, event_date.isocalendar().week),
            )
            tiempo_key = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO fact_sismos
                    (external_id, updated, event_time, magnitude, longitude, latitude,
                     depth_km, place, geografia_key, tiempo_key, source_topic)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (external_id) DO UPDATE
                SET updated = EXCLUDED.updated,
                    event_time = EXCLUDED.event_time,
                    magnitude = EXCLUDED.magnitude,
                    longitude = EXCLUDED.longitude,
                    latitude = EXCLUDED.latitude,
                    depth_km = EXCLUDED.depth_km,
                    place = EXCLUDED.place,
                    geografia_key = EXCLUDED.geografia_key,
                    tiempo_key = EXCLUDED.tiempo_key,
                    source_topic = EXCLUDED.source_topic,
                    ingested_at = CURRENT_TIMESTAMP
                WHERE EXCLUDED.updated > fact_sismos.updated
                """,
                (
                    event.external_id,
                    event.updated,
                    event.event_time,
                    event.magnitude,
                    event.longitude,
                    event.latitude,
                    event.depth_km,
                    event.place,
                    geography_key,
                    tiempo_key,
                    source_topic,
                ),
            )


def persist_quarantine(
    dsn: str,
    payload: Any,
    external_id: str | None,
    source_topic: str,
    partition: int,
    offset: int,
    dimension: str,
    reason_code: str,
    reason_detail: str,
) -> None:
    persist_quarantines(
        dsn,
        [
            (
                payload,
                external_id,
                source_topic,
                partition,
                offset,
                dimension,
                reason_code,
                reason_detail,
            )
        ],
    )


def persist_quarantines(
    dsn: str,
    failures: list[tuple[Any, str | None, str, int, int, str, str, str]],
) -> None:
    with psycopg2.connect(dsn) as connection:
        with connection.cursor() as cursor:
            for (
                payload,
                external_id,
                source_topic,
                partition,
                offset,
                dimension,
                reason_code,
                reason_detail,
            ) in failures:
                cursor.execute(
                    """
                    INSERT INTO cuarentena
                        (external_id, source_topic, quality_dimension, reason_code,
                         reason_detail, payload, kafka_partition, kafka_offset)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        external_id,
                        source_topic,
                        dimension,
                        reason_code,
                        reason_detail,
                        Json(payload),
                        partition,
                        offset,
                    ),
                )
