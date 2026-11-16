import calendar
import json
from datetime import datetime, timezone

import pytest

from api.app.serialize import JsonResponse, feature_from_row, finite_or_none, to_ms


def make_row(**overrides):
    row = {
        "id": "us7000abcd",
        "updated": datetime(2025, 3, 1, 12, 0, 5, tzinfo=timezone.utc),
        "time": datetime(2025, 3, 1, 11, 0, 0, 123000, tzinfo=timezone.utc),
        "mag": 3.2,
        "mag_type": "ml",
        "place": "Ejemplo, España",
        "longitude": -3.7,
        "latitude": 40.4,
        "depth_km": 12.0,
        "country_id": "ESP",
        "country_name": "España",
        "continent": "Europe",
        "subregion": "Southern Europe",
    }
    row.update(overrides)
    return row


def replay_row(**overrides):
    return make_row(
        replayed_at=datetime(2026, 1, 1, tzinfo=timezone.utc), is_synthetic=False, **overrides
    )


def test_to_ms_epoch_and_post_1970():
    assert to_ms(datetime(1970, 1, 1, tzinfo=timezone.utc)) == 0
    assert to_ms(datetime(2025, 3, 1, 11, 0, 0, 123000, tzinfo=timezone.utc)) == 1740826800123


def test_to_ms_pre_1970_is_exact():
    assert to_ms(datetime(1969, 12, 31, 23, 59, 59, 999000, tzinfo=timezone.utc)) == -1
    valdivia = datetime(1960, 5, 22, 19, 11, 20, 500000, tzinfo=timezone.utc)
    assert to_ms(valdivia) == calendar.timegm(valdivia.utctimetuple()) * 1000 + 500


def test_to_ms_returns_int():
    assert isinstance(to_ms(datetime(1969, 1, 1, tzinfo=timezone.utc)), int)


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), float("-inf"), "abc"])
def test_finite_or_none_discards_non_finite(value):
    assert finite_or_none(value) is None


def test_finite_or_none_keeps_numbers():
    assert finite_or_none(3.5) == 3.5
    assert finite_or_none(0) == 0.0


def test_feature_structure_and_coordinate_order():
    feature = feature_from_row(make_row(), replay=False)
    assert feature["type"] == "Feature"
    assert feature["id"] == "us7000abcd"
    assert feature["geometry"] == {"type": "Point", "coordinates": [-3.7, 40.4, 12.0]}
    props = feature["properties"]
    assert props["mag"] == 3.2
    assert props["magType"] == "ml"
    assert props["place"] == "Ejemplo, España"
    assert props["time"] == 1740826800123
    assert props["updated"] == 1740830405000
    assert props["country_id"] == "ESP"
    assert props["country_name"] == "España"
    assert props["continent"] == "Europe"
    assert props["subregion"] == "Southern Europe"


def test_live_mode_has_no_replay_properties():
    props = feature_from_row(make_row(), replay=False)["properties"]
    assert "replayed_at" not in props
    assert "synthetic" not in props


def test_null_magnitude_and_depth():
    feature = feature_from_row(make_row(mag=None, depth_km=None, mag_type=None, place=None), replay=False)
    assert feature["properties"]["mag"] is None
    assert feature["properties"]["magType"] is None
    assert feature["properties"]["place"] is None
    assert feature["geometry"]["coordinates"] == [-3.7, 40.4, None]


def test_nan_and_infinity_become_null():
    feature = feature_from_row(make_row(mag=float("nan"), depth_km=float("inf")), replay=False)
    assert feature["properties"]["mag"] is None
    assert feature["geometry"]["coordinates"][2] is None
    json.loads(JsonResponse(feature).body)  # serializes without error


def test_no_country():
    feature = feature_from_row(
        make_row(country_id=None, country_name=None, continent=None, subregion=None), replay=False
    )
    props = feature["properties"]
    assert props["country_id"] is None and props["country_name"] is None
    assert props["continent"] is None and props["subregion"] is None


def test_pre_1970_event_time():
    feature = feature_from_row(make_row(time=datetime(1969, 12, 31, 23, 59, 59, tzinfo=timezone.utc)), replay=False)
    assert feature["properties"]["time"] == -1000


def test_replay_adds_replayed_at_and_synthetic_false():
    props = feature_from_row(replay_row(), replay=True)["properties"]
    assert props["replayed_at"] == 1767225600000
    assert props["synthetic"] is False


def test_synthetic_by_flag():
    row = make_row(replayed_at=datetime(2026, 1, 1, tzinfo=timezone.utc), is_synthetic=True)
    assert feature_from_row(row, replay=True)["properties"]["synthetic"] is True


def test_synthetic_by_id_prefix():
    row = make_row(
        id="synthetic-0001", replayed_at=datetime(2026, 1, 1, tzinfo=timezone.utc), is_synthetic=False
    )
    assert feature_from_row(row, replay=True)["properties"]["synthetic"] is True


def test_json_response_is_compact_and_unescaped():
    body = JsonResponse({"place": "España", "n": [1, 2]}).body
    assert body == '{"place":"España","n":[1,2]}'.encode("utf-8")


def test_json_response_rejects_nan():
    with pytest.raises(ValueError):
        JsonResponse({"x": float("nan")})
