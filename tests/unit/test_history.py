"""Reading of replay batches (producer/app/replay.py; the replay itself is spec 005).

The downloader that used to live in producer/app/history.py was replaced by
the catalog-loader of spec 003, so these tests only cover reading JSONL lines.
"""

import json

from producer.app.replay import read_replay_events

EVENT_1900 = {
    "id": "historic-1900",
    "time": -2208988800000,
    "properties": {},
    "geometry": {"type": "Point", "coordinates": [0, 0, 1]},
}


def write_lines(path, *events) -> None:
    path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8", newline="\n")


def test_replay_reads_lines_and_tags_the_topic(tmp_path) -> None:
    path = tmp_path / "history.jsonl"
    write_lines(path, EVENT_1900)

    result = read_replay_events(path, "earthquakes.replay")

    assert result[0]["source_topic"] == "earthquakes.replay"
    assert result[0]["id"] == "historic-1900"


def test_replay_year_validation_is_optional(tmp_path) -> None:
    path = tmp_path / "history.jsonl"
    write_lines(path, EVENT_1900)

    assert read_replay_events(path, "earthquakes.replay", expected_year=1900)
