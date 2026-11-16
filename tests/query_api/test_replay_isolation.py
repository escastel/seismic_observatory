"""Loading or emptying the replay schema never changes what real mode answers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.types.json import Jsonb

from tests.db.helpers import Version

START = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
END = datetime(2026, 3, 2, 0, 0, tzinfo=timezone.utc)
PERIOD = {"start": "2026-03-01T00:00:00Z", "end": "2026-03-02T00:00:00Z"}


def version(event_id: str, event_time: datetime, **changes) -> Version:
    return Version(event_id, event_time=event_time, updated_at=event_time + timedelta(minutes=5), **changes)


def live_snapshot(api) -> dict:
    """Full real-mode answer with a fixed period; `generated` is the only moving value."""
    body = api.get("/api/eventos", **PERIOD).json()
    body["metadata"].pop("generated")
    snapshot = {"eventos": body}
    stats = api.get("/api/estadisticas", **PERIOD)
    if stats.status == 200:  # statistics arrive with a later task
        stats_body = stats.json()
        stats_body["metadata"].pop("generated", None)
        snapshot["estadisticas"] = stats_body
    return snapshot


def seed_live(api) -> None:
    for number in range(5):
        api.add_event(
            version(f"L{number}", START + timedelta(hours=number + 1), magnitude=3.0 + number * 0.5)
        )
    api.add_extraction()


def bulk_load_replay(api, count: int) -> None:
    """Thousands of replay events through the model function, in one connection."""
    with api._connect("writer", "replay") as conn:
        conn.autocommit = False
        with conn.transaction():
            for number in range(count):
                moment = START + timedelta(seconds=number * 7 % 86000)
                v = version(f"BULK{number}", moment, magnitude=2.0 + (number % 50) / 10)
                conn.execute(
                    """SELECT apply_event_version(
                        p_event_id => %s, p_source => %s, p_event_time => %s, p_updated_at => %s,
                        p_magnitude => %s, p_mag_type => %s, p_longitude => %s, p_latitude => %s,
                        p_depth_km => %s, p_place => %s, p_country_id => %s, p_quality_flags => %s,
                        p_payload => %s, p_kafka_topic => %s, p_kafka_partition => %s,
                        p_kafka_offset => %s, p_replayed_at => %s)""",
                    (
                        v.event_id, v.source, v.event_time, v.updated_at, v.magnitude, v.mag_type,
                        v.longitude, v.latitude, v.depth_km, v.place, v.country_id, v.quality_flags,
                        Jsonb(v.payload()), "earthquakes.replay", 0, 100_000 + number,
                        datetime.now(timezone.utc),
                    ),
                )


def test_thousands_of_replay_events_do_not_change_the_live_answer(api) -> None:
    seed_live(api)
    before = live_snapshot(api)
    assert before["eventos"]["metadata"]["total"] == 5

    bulk_load_replay(api, 3000)

    replay_total = api.get("/api/eventos", mode="replay", limit=1).json()["metadata"]["total"]
    assert replay_total == 3000
    assert live_snapshot(api) == before


def test_synthetic_only_in_replay_does_not_appear_in_live_mode(api) -> None:
    seed_live(api)
    api.add_event(version("synthetic-only-replay", START + timedelta(hours=3)), schema="replay")

    live = api.get("/api/eventos", **PERIOD).json()
    assert "synthetic-only-replay" not in [f["id"] for f in live["features"]]
    assert live["metadata"]["total"] == 5
    replay = api.get("/api/eventos", mode="replay").json()
    assert [f["id"] for f in replay["features"]] == ["synthetic-only-replay"]


def test_resetting_replay_leaves_live_equal_and_replay_empty(api) -> None:
    seed_live(api)
    for number in range(20):
        api.add_event(version(f"R{number}", START + timedelta(hours=number % 20)), schema="replay")
    before = live_snapshot(api)
    assert api.get("/api/eventos", mode="replay").json()["metadata"]["total"] == 20

    api.sql("SELECT replay.reset()", schema="replay", role="writer")

    assert live_snapshot(api) == before
    replay = api.get("/api/eventos", mode="replay").json()
    assert replay["features"] == []
    assert replay["metadata"]["total"] == 0
    assert replay["metadata"]["label"] == "REPRODUCCIÓN"
