"""GET /api/salud and the explicit errors when the database cannot answer."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from tests.db.helpers import Version


def ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def minutes_ago(minutes: int) -> datetime:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).replace(microsecond=0)


def test_healthy_system_reports_ok_with_last_ok_extraction(api) -> None:
    older, newest = minutes_ago(30), minutes_ago(5)
    api.add_extraction(requested_at=older)
    api.add_extraction(requested_at=newest)

    response = api.get("/api/salud")

    assert response.status == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok" and body["replay_database"] == "ok"
    assert body["last_ingestion"] == ms(newest)
    assert isinstance(body["generated"], int)


def test_failed_extractions_do_not_move_last_ingestion(api) -> None:
    good = minutes_ago(30)
    api.add_extraction(requested_at=good)
    api.add_extraction(requested_at=minutes_ago(10), outcome="http_error", http_status=503)
    api.add_extraction(requested_at=minutes_ago(5), outcome="timeout", http_status=None)

    assert api.get("/api/salud").json()["last_ingestion"] == ms(good)
    assert api.get("/api/eventos").json()["metadata"]["last_ingestion"] == ms(good)


def test_not_modified_does_move_last_ingestion(api) -> None:
    api.add_extraction(requested_at=minutes_ago(30))
    unchanged = minutes_ago(3)
    api.add_extraction(requested_at=unchanged, outcome="not_modified", http_status=304)

    assert api.get("/api/salud").json()["last_ingestion"] == ms(unchanged)


def test_recent_event_without_extraction_gives_null_last_ingestion(api) -> None:
    now = datetime.now(timezone.utc)
    api.add_event(Version("FRESH", updated_at=now - timedelta(minutes=1), event_time=now - timedelta(minutes=30)))

    assert api.get("/api/salud").json()["last_ingestion"] is None
    assert api.get("/api/eventos").json()["metadata"]["last_ingestion"] is None


def test_closed_pools_degrade_health_and_fail_data_endpoints_with_503(api) -> None:
    api.add_event(Version("E", updated_at=datetime.now(timezone.utc), event_time=minutes_ago(20)))
    api.close_pools()

    health = api.get("/api/salud")
    assert health.status == 200
    assert health.json()["status"] == "degraded"
    assert health.json()["database"] == "unavailable"
    assert health.json()["replay_database"] == "unavailable"
    assert health.json()["last_ingestion"] is None

    for path in ("/api/eventos", "/api/estadisticas"):
        response = api.get(path)
        assert response.status == 503, path
        body = response.json()
        assert body["error"] == "database_unavailable"
        assert "features" not in body
        response = api.get(path, mode="replay")
        assert response.status == 503, path
        assert response.json()["error"] == "database_unavailable"


def test_pools_not_open_yet_are_also_unavailable(api) -> None:
    api.set_pools_none()

    assert api.get("/api/salud").json()["status"] == "degraded"
    response = api.get("/api/eventos")
    assert response.status == 503
    assert response.json()["error"] == "database_unavailable"


def test_health_recovers_after_reopening(api) -> None:
    api.close_pools()
    assert api.get("/api/salud").json()["status"] == "degraded"

    api.reopen_pools()

    body = api.get("/api/salud").json()
    assert body["status"] == "ok"
    assert body["database"] == "ok" and body["replay_database"] == "ok"
    assert api.get("/api/eventos").status == 200


def test_health_body_leaks_no_credentials_or_host(api) -> None:
    api.close_pools()
    texts = [api.get("/api/salud").text.lower()]
    api.reopen_pools()
    texts.append(api.get("/api/salud").text.lower())

    secrets = ["observatory_reader", "observatory_writer", "observatory_owner", "password", "postgres://"]
    for name in ("PGHOST", "DB_READER_PASSWORD"):
        value = os.environ.get(name)
        if value and len(value) > 3:
            secrets.append(value.lower())
    for text in texts:
        for secret in secrets:
            assert secret not in text, secret
