"""Bounded and paged responses of GET /api/eventos (spec 006, US5).

The maximum is injected through the harness (app.state.max_features), as the configuration does.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.db.helpers import Version

START = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
END = datetime(2026, 3, 2, 0, 0, tzinfo=timezone.utc)
REPLAY_BASE = datetime(2025, 6, 10, 0, 0, tzinfo=timezone.utc)
MAX_FEATURES = 50


def iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def make_events(api, count: int, base: datetime, schema: str, group: int = 7) -> list[tuple[int, str]]:
    """Insert `count` events; every `group` consecutive ones share the same time (ties)."""
    expected = []
    for number in range(count):
        event_time = base + timedelta(minutes=number // group)
        event_id = f"E{number:03d}"
        api.add_event(
            Version(event_id, event_time=event_time, updated_at=event_time + timedelta(minutes=5)),
            schema=schema,
        )
        expected.append((int(event_time.timestamp() * 1000), event_id))
    # time descending, id ascending
    return sorted(expected, key=lambda item: (-item[0], item[1]))


def window(mode: str) -> dict[str, str]:
    if mode == "replay":
        return {"mode": "replay"}
    return {"start": iso(START), "end": iso(END)}


def walk(api, mode: str, **params) -> tuple[list[dict], list[dict]]:
    """Follow next_offset until null; return (features, metadata of each page)."""
    features: list[dict] = []
    pages: list[dict] = []
    offset = 0
    for _ in range(100):  # guard against an endless loop
        response = api.get("/api/eventos", **window(mode), **params, offset=offset)
        assert response.status == 200
        body = response.json()
        pages.append(body["metadata"])
        features.extend(body["features"])
        if body["metadata"]["next_offset"] is None:
            return features, pages
        offset = body["metadata"]["next_offset"]
    raise AssertionError("next_offset never became null")


@pytest.mark.parametrize(
    ("mode", "schema", "base", "count", "maximum"),
    [("live", "core", START, 130, MAX_FEATURES), ("replay", "replay", REPLAY_BASE, 60, 25)],
)
def test_walking_the_pages_visits_every_event_once_in_order(api, mode, schema, base, count, maximum) -> None:
    api.set_max_features(maximum)
    expected = make_events(api, count, base, schema)

    first = api.get("/api/eventos", **window(mode)).json()["metadata"]
    assert first["limit"] == maximum
    assert first["count"] == maximum
    assert first["total"] == count
    assert first["truncated"] is True
    assert first["next_offset"] == maximum

    features, pages = walk(api, mode)

    assert [f["id"] for f in features] == [event_id for _, event_id in expected]
    assert len({f["id"] for f in features}) == count
    times = [f["properties"]["time"] for f in features]
    assert times == sorted(times, reverse=True)
    assert all(page["total"] == count for page in pages)
    assert pages[-1]["truncated"] is False and pages[-1]["next_offset"] is None
    assert sum(page["count"] for page in pages) == count


def test_ties_across_a_page_boundary_lose_and_repeat_nothing(api) -> None:
    api.set_max_features(MAX_FEATURES)
    # 7 events per instant: the boundary at 50 falls inside a group of equal times
    expected = make_events(api, 130, START, "core", group=7)
    boundary = MAX_FEATURES
    assert expected[boundary - 1][0] == expected[boundary][0]

    first = api.get("/api/eventos", **window("live")).json()["features"]
    second = api.get("/api/eventos", **window("live"), offset=boundary).json()["features"]

    assert [f["id"] for f in first] == [e for _, e in expected[:boundary]]
    assert [f["id"] for f in second][:5] == [e for _, e in expected[boundary : boundary + 5]]
    assert not {f["id"] for f in first} & {f["id"] for f in second}


def test_fewer_events_than_the_maximum_is_not_truncated(api) -> None:
    api.set_max_features(MAX_FEATURES)
    make_events(api, 12, START, "core")

    meta = api.get("/api/eventos", **window("live")).json()["metadata"]

    assert meta["truncated"] is False
    assert meta["total"] == meta["count"] == 12
    assert meta["next_offset"] is None


def test_exactly_the_maximum_is_not_truncated(api) -> None:
    api.set_max_features(10)
    make_events(api, 10, START, "core")

    meta = api.get("/api/eventos", **window("live")).json()["metadata"]

    assert (meta["count"], meta["total"], meta["truncated"], meta["next_offset"]) == (10, 10, False, None)


@pytest.mark.parametrize("mode", ["live", "replay"])
def test_limit_above_the_maximum_is_422(api, mode) -> None:
    api.set_max_features(MAX_FEATURES)

    response = api.get("/api/eventos", **window(mode), limit=MAX_FEATURES + 1)

    assert response.status == 422
    body = response.json()
    assert body["error"] == "invalid_parameters"
    assert body["detail"][0]["param"] == "limit"
    assert api.get("/api/eventos", **window(mode), limit=MAX_FEATURES).status == 200


def test_limit_zero_and_negative_offset_are_422(api) -> None:
    for params, name in (({"limit": 0}, "limit"), ({"offset": -1}, "offset")):
        response = api.get("/api/eventos", **window("live"), **params)
        assert response.status == 422
        assert response.json()["detail"][0]["param"] == name


@pytest.mark.parametrize(
    ("mode", "schema", "base"), [("live", "core", START), ("replay", "replay", REPLAY_BASE)]
)
def test_page_beyond_the_end_is_200_and_empty(api, mode, schema, base) -> None:
    api.set_max_features(MAX_FEATURES)
    make_events(api, 8, base, schema)

    response = api.get("/api/eventos", **window(mode), offset=500)

    assert response.status == 200
    body = response.json()
    assert body["features"] == []
    meta = body["metadata"]
    assert meta["count"] == 0
    assert meta["total"] == 8
    assert meta["truncated"] is False
    assert meta["next_offset"] is None
    assert meta["offset"] == 500


def test_default_limit_is_the_configured_maximum(api) -> None:
    api.set_max_features(20)
    make_events(api, 30, START, "core")

    meta = api.get("/api/eventos", **window("live")).json()["metadata"]

    assert meta["limit"] == 20 and meta["count"] == 20 and meta["truncated"] is True
