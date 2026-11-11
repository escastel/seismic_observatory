"""Durable producer publication state."""

from __future__ import annotations

from datetime import datetime

import psycopg2


def ensure_state_table(dsn: str) -> None:
    with psycopg2.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_state (
                    external_id TEXT PRIMARY KEY,
                    updated TIMESTAMPTZ NOT NULL,
                    published_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )


def should_publish(dsn: str, external_id: str, updated: datetime) -> bool:
    with psycopg2.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT updated
                FROM ingestion_state
                WHERE external_id = %s
                """,
                (external_id,),
            )
            current = cursor.fetchone()
    return current is None or updated > current[0]


def mark_published(dsn: str, external_id: str, updated: datetime) -> None:
    with psycopg2.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ingestion_state (external_id, updated)
                VALUES (%s, %s)
                ON CONFLICT (external_id) DO UPDATE
                SET updated = EXCLUDED.updated, published_at = CURRENT_TIMESTAMP
                WHERE EXCLUDED.updated > ingestion_state.updated
                """,
                (external_id, updated),
            )
