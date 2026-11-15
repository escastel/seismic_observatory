from producer.app.history import fetch_years, write_jsonl
from producer.app.replay import read_replay_events


def test_write_history_jsonl_and_replay_infers_year(tmp_path) -> None:
    event = {
        "id": "historic-1900",
        "time": -2208988800000,
        "properties": {},
        "geometry": {"type": "Point", "coordinates": [0, 0, 1]},
    }
    path = tmp_path / "history.jsonl"
    assert write_jsonl([event], path) == 1
    result = read_replay_events(path, "earthquakes.replay")
    assert result[0]["source_topic"] == "earthquakes.replay"
    assert result[0]["id"] == "historic-1900"


def test_replay_year_validation_is_optional(tmp_path) -> None:
    path = tmp_path / "history.jsonl"
    path.write_text(
        '{"id":"historic-1900","time":-2208988800000,"properties":{},'
        '"geometry":{"type":"Point","coordinates":[0,0,1]}}\n',
        encoding="utf-8",
    )
    assert read_replay_events(path, "earthquakes.replay", expected_year=1900)


def test_fetch_years_retrieves_an_inclusive_range(monkeypatch) -> None:
    requested: list[int] = []

    def fake_fetch_year(year: int, timeout: int = 60) -> list[dict]:
        requested.append(year)
        return [{"id": f"historic-{year}"}]

    monkeypatch.setattr("producer.app.history.fetch_year", fake_fetch_year)

    result = fetch_years(2024, 2026)

    assert requested == [2024, 2025, 2026]
    assert list(result) == [2024, 2025, 2026]
