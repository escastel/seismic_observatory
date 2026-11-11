from unittest.mock import Mock

from producer.app.feed import fetch_feed


def test_fetch_feed_keeps_only_earthquake_features(monkeypatch) -> None:
    response = Mock(status_code=200)
    response.json.return_value = {
        "type": "FeatureCollection",
        "features": [
            {"id": "eq", "properties": {"type": "earthquake"}},
            {"id": "other", "properties": {"type": "quarry blast"}},
        ],
    }
    response.raise_for_status.return_value = None
    monkeypatch.setattr("producer.app.feed.requests.get", lambda *args, **kwargs: response)

    result = fetch_feed("https://example.test/feed")

    assert [feature["id"] for feature in result["features"]] == ["eq"]


def test_fetch_feed_retries_transient_http_failure(monkeypatch) -> None:
    transient = Mock(status_code=503, headers={})
    transient.raise_for_status.side_effect = RuntimeError("unreachable")
    success = Mock(status_code=200, headers={})
    success.json.return_value = {"type": "FeatureCollection", "features": []}
    success.raise_for_status.return_value = None
    responses = iter([transient, success])
    monkeypatch.setattr("producer.app.feed.requests.get", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr("producer.app.feed.time.sleep", lambda _: None)

    assert fetch_feed("https://example.test/feed", max_retries=1)["features"] == []
