"""USGS HTTP client: retries, Retry-After, timeouts and outcome classification (FR-001, FR-002, FR-015)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import pytest

from common.settings import UsgsSettings
from producer.app.usgs import FetchResult, fetch
from tests.support.usgs_stub import FakeUsgs, Reply, collection, feature

FEED = "/feed"


def settings(timeout: int = 5, attempts: int = 4) -> UsgsSettings:
    return UsgsSettings(
        feed_url=None,
        catalog_url="http://unused",
        timeout_seconds=timeout,
        max_attempts=attempts,
        user_agent="observatory-test/1.0",
    )


class Waits:
    """Records the waits fetch() asks for instead of sleeping."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


@pytest.fixture
def usgs():
    with FakeUsgs() as stub:
        yield stub


def get(usgs: FakeUsgs, waits: Waits | None = None, **kwargs) -> FetchResult:
    options = {"settings": settings(), "sleep": waits or Waits()}
    options.update(kwargs)
    return fetch(usgs.url(FEED), **options)


def test_success_returns_body_payload_and_metadata(usgs: FakeUsgs) -> None:
    body = collection([feature("E1")])
    usgs.script(FEED, Reply.json(body))

    result = get(usgs)

    assert result.outcome == "ok"
    assert result.http_status == 200
    assert result.attempt_count == 1
    assert result.duration_ms >= 0
    assert result.payload == body
    assert result.body is not None and b'"E1"' in result.body
    assert result.last_modified == "Sun, 15 Nov 2026 01:20:53 GMT"
    assert result.error_detail is None
    assert result.url == usgs.url(FEED)
    assert result.requested_at.tzinfo is not None


def test_user_agent_and_conditional_header(usgs: FakeUsgs) -> None:
    usgs.script(FEED, Reply.json(collection([]), conditional=True))

    first = get(usgs)
    second = get(usgs, if_modified_since=first.last_modified)

    assert first.outcome == "ok"
    assert second.outcome == "not_modified"
    assert second.http_status == 304
    assert second.body is None
    requests = usgs.requests_to(FEED)
    assert all(request.headers["User-Agent"] == "observatory-test/1.0" for request in requests)
    assert "If-Modified-Since" not in requests[0].headers
    assert requests[1].headers["If-Modified-Since"] == first.last_modified


def test_server_error_then_success_counts_attempts(usgs: FakeUsgs) -> None:
    usgs.script(FEED, Reply.text("busy", status=503), Reply.json(collection([])))
    waits = Waits()

    result = get(usgs, waits)

    assert result.outcome == "ok"
    assert result.attempt_count == 2
    assert waits.calls == [1]


def test_persistent_server_error_uses_every_attempt(usgs: FakeUsgs) -> None:
    usgs.script(FEED, Reply.text("busy", status=503))
    waits = Waits()

    result = get(usgs, waits)

    assert result.outcome == "http_error"
    assert result.http_status == 503
    assert result.attempt_count == 4
    assert waits.calls == [1, 2, 4]
    assert "503" in result.error_detail
    assert len(usgs.requests_to(FEED)) == 4


def test_retry_after_in_seconds_is_respected(usgs: FakeUsgs) -> None:
    usgs.script(FEED, Reply.text("slow down", status=429, headers={"Retry-After": "2"}), Reply.json(collection([])))
    waits = Waits()

    result = get(usgs, waits)

    assert result.outcome == "ok"
    assert waits.calls == [2]


def test_retry_after_never_shortens_the_backoff(usgs: FakeUsgs) -> None:
    replies = [Reply.text("slow", status=429, headers={"Retry-After": "1"})] * 3 + [Reply.json(collection([]))]
    usgs.script(FEED, *replies)
    waits = Waits()

    get(usgs, waits)

    assert waits.calls == [1, 2, 4]


def test_retry_after_as_http_date_is_converted(usgs: FakeUsgs) -> None:
    later = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=30), usegmt=True)
    usgs.script(FEED, Reply.text("slow down", status=429, headers={"Retry-After": later}), Reply.json(collection([])))
    waits = Waits()

    get(usgs, waits)

    assert len(waits.calls) == 1
    assert 25 <= waits.calls[0] <= 31


def test_long_retry_after_is_not_retried_within_the_cycle(usgs: FakeUsgs) -> None:
    usgs.script(FEED, Reply.text("come back later", status=429, headers={"Retry-After": "300"}))
    waits = Waits()

    result = get(usgs, waits)

    assert result.outcome == "http_error"
    assert result.http_status == 429
    assert result.attempt_count == 1
    assert result.retry_after_seconds == 300
    assert waits.calls == []
    assert "Retry-After" in result.error_detail


def test_timeout_is_classified_and_retried(usgs: FakeUsgs) -> None:
    usgs.script(FEED, Reply(delay=3))
    waits = Waits()

    result = get(usgs, waits, settings=settings(timeout=1, attempts=2))

    assert result.outcome == "timeout"
    assert result.http_status is None
    assert result.attempt_count == 2
    assert waits.calls == [1]


def test_connection_refused_is_a_timeout_outcome() -> None:
    with FakeUsgs() as stub:
        url = stub.url(FEED)
    result = fetch(url, settings=settings(attempts=1), sleep=Waits())
    assert result.outcome == "timeout"
    assert "connection" in result.error_detail.lower()


def test_client_errors_are_not_retried(usgs: FakeUsgs) -> None:
    usgs.script(FEED, Reply.text("Error 400: Bad Request\n\n27066 matching events exceeds search limit of 20000", status=400))
    waits = Waits()

    result = get(usgs, waits)

    assert result.outcome == "http_error"
    assert result.http_status == 400
    assert result.attempt_count == 1
    assert waits.calls == []
    assert result.body is not None and b"exceeds search limit" in result.body
    assert "exceeds search limit" in result.error_detail


def test_body_that_is_not_json(usgs: FakeUsgs) -> None:
    usgs.script(FEED, Reply.text("<html>maintenance</html>"))

    result = get(usgs)

    assert result.outcome == "invalid_json"
    assert result.http_status == 200
    assert result.body == b"<html>maintenance</html>"
    assert result.payload is None
    assert result.attempt_count == 1


def test_nan_literal_is_not_json(usgs: FakeUsgs) -> None:
    usgs.script(FEED, Reply(body=b'{"type":"FeatureCollection","features":[{"mag":NaN}]}'))

    assert get(usgs).outcome == "invalid_json"


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "Feature", "features": []},
        {"type": "FeatureCollection"},
        {"type": "FeatureCollection", "features": "none"},
        [1, 2, 3],
    ],
    ids=["wrong-type", "no-features", "features-not-a-list", "not-an-object"],
)
def test_json_without_the_collection_structure(usgs: FakeUsgs, payload) -> None:
    usgs.script(FEED, Reply.json(payload))

    result = get(usgs)

    assert result.outcome == "invalid_structure"
    assert result.body is not None
    assert result.payload is None
    assert result.error_detail


def test_count_responses_are_validated_as_counts(usgs: FakeUsgs) -> None:
    usgs.script("/count", Reply.json({"count": 1413, "maxAllowed": 20000}), Reply.json({"total": 3}))

    good = fetch(usgs.url("/count"), settings=settings(), sleep=Waits(), expect="count")
    bad = fetch(usgs.url("/count"), settings=settings(), sleep=Waits(), expect="count")

    assert good.outcome == "ok" and good.payload == {"count": 1413, "maxAllowed": 20000}
    assert bad.outcome == "invalid_structure"


def test_query_parameters_are_part_of_the_recorded_url(usgs: FakeUsgs) -> None:
    usgs.script(FEED, Reply.json(collection([])))

    result = get(usgs, params={"starttime": "2025-01-01T00:00:00Z", "minmagnitude": 4})

    assert "starttime=2025-01-01T00%3A00%3A00Z" in result.url
    assert "minmagnitude=4" in result.url
    assert usgs.requests_to(FEED)[0].params["minmagnitude"] == "4"


def test_duration_includes_every_attempt(usgs: FakeUsgs) -> None:
    usgs.script(FEED, Reply(delay=0.3, status=503), Reply.json(collection([])))

    result = get(usgs)

    assert result.attempt_count == 2
    assert result.duration_ms >= 300
