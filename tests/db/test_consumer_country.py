"""Country assignment end to end: real MessageHandler, real SpatialEnricher and the delivered catalog
(US3: FR-019 to FR-022; enunciado §11 «Evento marítimo»)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import psycopg
import pytest

pytest.importorskip("geopandas")

from common.settings import TopicNames  # noqa: E402
from consumer.app.main import MessageHandler  # noqa: E402
from consumer.app.spatial import SpatialEnricher  # noqa: E402
from tests.db.async_support import writer_pool  # noqa: E402
from tests.db.test_consumer_persistence import FakeMessage  # noqa: E402
from tests.db.test_consumer_rules import coords, flat  # noqa: E402

CATALOG = Path(__file__).resolve().parents[2] / "frontend" / "public" / "datos" / "paises.geojson"
ENRICHER = SpatialEnricher(str(CATALOG))


def process(test_database: str, messages: list[dict]) -> list[str]:
    async def run() -> list[str]:
        pool = await writer_pool(test_database)
        try:
            handler = MessageHandler({"core": pool, "replay, core": pool}, TopicNames(), ENRICHER)
            return [await handler(FakeMessage("earthquakes.live", n, json.dumps(m).encode())) for n, m in enumerate(messages)]
        finally:
            await pool.close()

    return asyncio.run(run())


def country_of(conn: psycopg.Connection, event_id: str) -> tuple:
    return conn.execute("SELECT country_id, quality_flags FROM core.event_current WHERE event_id = %s", (event_id,)).fetchone()


def test_interior_point_gets_an_existing_country(test_database: str, owner_conn: psycopg.Connection) -> None:
    process(test_database, [flat("MAD", geometry=coords(-3.70, 40.42, 10.0)), flat("TYO", geometry=coords(139.69, 35.69, 30.0))])

    assert country_of(owner_conn, "MAD") == ("ESP", [])
    assert country_of(owner_conn, "TYO") == ("JPN", [])
    unknown = owner_conn.execute(
        "SELECT count(*) FROM core.event_current e LEFT JOIN core.dim_country c USING (country_id) "
        "WHERE e.country_id IS NOT NULL AND c.country_id IS NULL").fetchone()[0]
    assert unknown == 0


def test_maritime_event_has_no_country_and_stays_in_the_analysis(test_database: str, owner_conn: psycopg.Connection) -> None:
    outcomes = process(test_database, [flat("SEA", geometry=coords(-120.0, -20.0, 10.0))])

    assert outcomes == ["new"]
    assert country_of(owner_conn, "SEA") == (None, [])
    assert owner_conn.execute("SELECT count(*) FROM core.quarantine").fetchone()[0] == 0
    assert owner_conn.execute("SELECT count(*) FROM core.event_current WHERE country_id IS NULL").fetchone()[0] == 1


def test_the_country_never_comes_from_the_place_text(test_database: str, owner_conn: psycopg.Connection) -> None:
    process(test_database, [flat("LIAR", place="10 km S of Madrid, Spain", geometry=coords(-120.0, -20.0, 10.0))])
    assert country_of(owner_conn, "LIAR")[0] is None


def test_assignment_is_repeatable(test_database: str, owner_conn: psycopg.Connection) -> None:
    points = [(-70.1, -33.4), (-155.3, 19.4), (95.0, 3.2), (-120.0, -20.0), (30.0, 50.0)]
    process(test_database, [flat(f"P{n}", geometry=coords(lon, lat, 5.0)) for n, (lon, lat) in enumerate(points)])
    first = owner_conn.execute("SELECT event_id, country_id FROM core.event_current ORDER BY 1").fetchall()
    owner_conn.execute("TRUNCATE core.event_current, core.event_version, core.message_log CASCADE")
    process(test_database, [flat(f"P{n}", geometry=coords(lon, lat, 5.0)) for n, (lon, lat) in enumerate(points)])
    assert owner_conn.execute("SELECT event_id, country_id FROM core.event_current ORDER BY 1").fetchall() == first
