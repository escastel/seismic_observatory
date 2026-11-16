from datetime import datetime, timezone
from unittest import mock

from producer.app.replay.message import build_replay_message
from producer.app.replay.synthetic import synthetic_items


def test_seven_items_in_fixed_order():
    items = synthetic_items()
    assert len(items) == 7
    assert [i.event_id for i in items] == [
        "synthetic-replay-first",
        "synthetic-replay-first",
        "synthetic-replay-revised",
        "synthetic-replay-revised",
        "synthetic-replay-stale",
        "synthetic-replay-stale",
        "synthetic-replay-bad-coordinates",
    ]


def test_first_is_repeated_exactly():
    items = synthetic_items()
    assert items[0].feature == items[1].feature


def test_revision_changes_magnitude_and_updated():
    items = synthetic_items()
    v1, v2 = items[2].feature["properties"], items[3].feature["properties"]
    assert (v1["mag"], v2["mag"]) == (4.1, 4.4)
    assert v1["updated"] < v2["updated"]


def test_stale_old_version_is_older_and_arrives_last():
    items = synthetic_items()
    new, old = items[4].feature["properties"], items[5].feature["properties"]
    assert old["updated"] < new["updated"]


def test_bad_coordinates_latitude():
    assert synthetic_items()[6].feature["geometry"]["coordinates"][1] == 145.0


def test_prefix_and_dates_independent_of_now():
    before = synthetic_items()
    with mock.patch("producer.app.replay.synthetic.datetime") as fake:
        fake.now.return_value = datetime(2030, 1, 1, tzinfo=timezone.utc)
        after = synthetic_items()
    assert [i.feature for i in before] == [i.feature for i in after]
    for item in before:
        assert item.event_id.startswith("synthetic-replay-")
        assert item.feature["properties"]["time"] == 1749988800000  # 2025-06-15 12:00 UTC


def test_messages_carry_synthetic_marks():
    for item in synthetic_items():
        msg = build_replay_message(
            item.feature,
            extraction_id=None,
            replayed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            run="r1",
            synthetic_case=item.synthetic_case,
        )
        assert msg["synthetic"] is True
        assert msg["synthetic_case"] == item.synthetic_case
        assert msg["mode"] == "replay"
