"""Real HTTP/Kafka end-to-end verification for a running local Compose stack."""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from uuid import uuid4

import pytest

requests = pytest.importorskip("requests")
aiokafka = pytest.importorskip("aiokafka")
KafkaError = aiokafka.errors.KafkaError


BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8000")
KAFKA_BOOTSTRAP = os.getenv("E2E_KAFKA_BOOTSTRAP", "localhost:29092")
RAW_TOPIC = os.getenv("KAFKA_RAW_TOPIC", "terremotos_raw")
REPLAY_TOPIC = os.getenv("KAFKA_REPLAY_TOPIC", "terremotos_replay")


def _event(event_id: str, topic: str, timestamp_ms: int) -> dict:
    return {
        "id": event_id,
        "updated": timestamp_ms,
        "time": timestamp_ms,
        "mag": 4.5,
        "place": f"E2E {topic}",
        "geometry": {"type": "Point", "coordinates": [-70.0, -33.0, 10.0]},
        "source_topic": topic,
    }


async def _publish_pair(raw_event: dict, replay_event: dict) -> None:
    producer = aiokafka.AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    await producer.start()
    try:
        await asyncio.gather(
            producer.send_and_wait(
                RAW_TOPIC,
                key=raw_event["id"].encode(),
                value=json.dumps(raw_event).encode(),
            ),
            producer.send_and_wait(
                REPLAY_TOPIC,
                key=replay_event["id"].encode(),
                value=json.dumps(replay_event).encode(),
            ),
        )
    finally:
        await producer.stop()


def test_real_e2e_processes_raw_and_replay_topics() -> None:
    try:
        health = requests.get(f"{BASE_URL}/api/health", timeout=2)
    except requests.RequestException as exc:
        pytest.skip(f"local FastAPI is unavailable: {exc}")
    assert health.status_code == 200

    timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000) - 10_000
    raw_id = f"e2e-raw-{uuid4()}"
    replay_id = f"e2e-replay-{uuid4()}"
    try:
        asyncio.run(
            _publish_pair(
                _event(raw_id, RAW_TOPIC, timestamp_ms),
                _event(replay_id, REPLAY_TOPIC, timestamp_ms),
            )
        )
    except (KafkaError, OSError, RuntimeError) as exc:
        pytest.skip(f"local Kafka is unavailable: {exc}")

    deadline = time.monotonic() + 30
    geojson = None
    while time.monotonic() < deadline:
        response = requests.get(
            f"{BASE_URL}/api/eventos",
            params={"format": "geojson", "limit": 10000},
            timeout=5,
        )
        if response.status_code == 200:
            candidate = response.json()
            features = candidate.get("features", [])
            ids = {feature.get("id") for feature in features}
            sources = {
                feature.get("properties", {}).get("source_topic")
                for feature in features
            }
            if {raw_id, replay_id} <= ids and {RAW_TOPIC, REPLAY_TOPIC} <= sources:
                geojson = candidate
                break
        time.sleep(0.5)

    assert geojson is not None, "both raw and replay events were not queryable within 30 seconds"
    assert geojson["type"] == "FeatureCollection"
    assert all(feature["type"] == "Feature" for feature in geojson["features"])

    countries = requests.get(f"{BASE_URL}/api/estadisticas/paises", timeout=5)
    timeline = requests.get(
        f"{BASE_URL}/api/estadisticas/timeline",
        params={"bucket": "day"},
        timeout=5,
    )
    assert countries.status_code == 200
    assert timeline.status_code == 200
    assert isinstance(countries.json()["items"], list)
    assert isinstance(timeline.json()["items"], list)
