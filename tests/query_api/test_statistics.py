"""Behavior of GET /api/estadisticas against the real test database (spec 006, US4)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.db.helpers import Version

START = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
END = datetime(2026, 3, 2, 0, 0, tzinfo=timezone.utc)
T2025 = datetime(2025, 6, 10, 12, 0, tzinfo=timezone.utc)
LABEL = "REPRODUCCIÓN"
NO_COUNTRY = "Sin país asignado"


def iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def version(event_id: str, event_time: datetime, **changes) -> Version:
    changes.setdefault("updated_at", event_time + timedelta(minutes=5))
    return Version(event_id, event_time=event_time, **changes)


def stats(api, **params) -> dict:
    response = api.get("/api/estadisticas", **params)
    assert response.status == 200, response.text
    return response.json()


def day_params() -> dict[str, str]:
    return {"start": iso(START), "end": iso(END)}


# --- same filter as the map --------------------------------------------------------------


FILTER_BATTERY = [
    {},
    {"start": iso(START), "end": iso(END)},
    {"start": iso(START)},
    {"end": iso(END)},
    {"min_mag": "4"},
    {"country_id": "ESP"},
    {"start": iso(START), "end": iso(END), "min_mag": "3", "country_id": "ESP"},
    {"min_mag": "100"},
    {"country_id": "FRA"},
]


@pytest.mark.parametrize("mode", ["live", "replay"])
def test_total_equals_the_map_total_for_every_filter_combination(api, mode) -> None:
    schema = "core" if mode == "live" else "replay"
    now = datetime.now(timezone.utc)
    specs = [
        ("A", START + timedelta(hours=1), 5.0, "ESP"),
        ("B", START + timedelta(hours=2), 3.0, "ESP"),
        ("C", START + timedelta(hours=3), 4.5, "JPN"),
        ("D", START + timedelta(hours=4), None, "ESP"),
        ("E", START + timedelta(hours=5), 2.0, None),
        ("F", END + timedelta(hours=1), 6.0, "ESP"),
        ("G", now - timedelta(hours=2), 4.0, "ESP"),
    ]
    for event_id, event_time, magnitude, country in specs:
        api.add_event(version(event_id, event_time, magnitude=magnitude, country_id=country), schema=schema)

    for params in FILTER_BATTERY:
        merged = {"mode": mode, **params}
        events = api.get("/api/eventos", **merged).json()
        body = stats(api, **merged)
        assert body["total"] == events["metadata"]["total"], params
        assert body["period"]["default_applied"] == events["metadata"]["period"]["default_applied"], params
        assert sum(item["count"] for item in body["hourly"]["items"]) == body["total"], params
        assert sum(item["count"] for item in body["by_country"]["items"]) == body["total"], params


# --- hourly windows ----------------------------------------------------------------------


def test_hour_boundaries_belong_to_the_hour_that_starts_there(api) -> None:
    ten = START + timedelta(hours=10)
    api.add_event(version("H1", ten))
    api.add_event(version("H2", ten + timedelta(minutes=59, seconds=59, milliseconds=999)))
    api.add_event(version("H3", ten + timedelta(hours=1)))

    body = stats(api, start=iso(ten), end=iso(ten + timedelta(hours=2)))

    ms = int(ten.timestamp() * 1000)
    assert body["hourly"]["items"] == [{"start": ms, "count": 2}, {"start": ms + 3_600_000, "count": 1}]
    assert body["total"] == 3


def test_empty_hours_are_present_with_zero(api) -> None:
    api.add_event(version("X1", START + timedelta(hours=10, minutes=30)))
    api.add_event(version("X2", START + timedelta(hours=13, minutes=30)))

    body = stats(api, start=iso(START + timedelta(hours=10)), end=iso(START + timedelta(hours=14)))

    assert [item["count"] for item in body["hourly"]["items"]] == [1, 0, 0, 1]
    starts = [item["start"] for item in body["hourly"]["items"]]
    assert all(b - a == 3_600_000 for a, b in zip(starts, starts[1:]))


def test_more_than_10000_windows_is_422(api) -> None:
    response = api.get("/api/estadisticas", start="2020-01-01T00:00:00Z", end="2026-01-01T00:00:00Z")

    assert response.status == 422
    body = response.json()
    assert body["error"] == "invalid_parameters"
    assert body["detail"][0]["param"] and body["detail"][0]["message"]


# --- countries ---------------------------------------------------------------------------


def test_events_without_country_are_their_own_category(api) -> None:
    api.add_event(version("S1", START + timedelta(hours=1), country_id="ESP"))
    api.add_event(version("S2", START + timedelta(hours=2), country_id=None, place="Mid-Atlantic Ridge"))
    api.add_event(version("S3", START + timedelta(hours=3), country_id=None, place="Mid-Atlantic Ridge"))

    body = stats(api, **day_params())

    items = {item["country_id"]: item for item in body["by_country"]["items"]}
    assert items[None]["country_name"] == NO_COUNTRY and items[None]["count"] == 2
    assert items["ESP"]["count"] == 1 and items["ESP"]["country_name"]
    assert sum(item["count"] for item in body["by_country"]["items"]) == body["total"] == 3


# --- distributions -----------------------------------------------------------------------


def test_null_magnitudes_and_depths_are_unvalued_and_everything_adds_up(api) -> None:
    api.add_event(version("V1", START + timedelta(hours=1), magnitude=4.2, depth_km=10.0))
    api.add_event(version("V2", START + timedelta(hours=2), magnitude=None, depth_km=80.0))
    api.add_event(version("V3", START + timedelta(hours=3), magnitude=5.9, depth_km=None))
    api.add_event(version("V4", START + timedelta(hours=4), magnitude=None, depth_km=None))

    body = stats(api, **day_params())

    mags, depths = body["magnitude_distribution"], body["depth_distribution"]
    assert mags["unvalued"] == 2 and depths["unvalued"] == 2
    assert sum(i["count"] for i in mags["items"]) + mags["unvalued"] == body["total"] == 4
    assert sum(i["count"] for i in depths["items"]) + depths["unvalued"] == body["total"]
    assert mags["unit"] and depths["unit"] == "km"
    bins = {(i["from"], i["to"]): i["count"] for i in mags["items"]}
    assert bins[(4, 5)] == 1 and bins[(5, 6)] == 1


def test_negative_magnitude_is_kept_in_its_bin(api) -> None:
    api.add_event(version("NEG", START + timedelta(hours=1), magnitude=-0.5))
    api.add_event(version("POS", START + timedelta(hours=2), magnitude=0.3))

    body = stats(api, **day_params())

    bins = {(i["from"], i["to"]): i["count"] for i in body["magnitude_distribution"]["items"]}
    assert bins[(-1, 0)] == 1
    assert bins[(0, 1)] == 1
    assert body["magnitude_distribution"]["unvalued"] == 0


def test_depth_bins_by_range(api) -> None:
    for number, depth in enumerate([5.0, 69.9, 70.0, 299.0, 300.0, 650.0, -1.0]):
        api.add_event(version(f"D{number}", START + timedelta(hours=1 + number), depth_km=depth))

    body = stats(api, **day_params())

    by_label = {item["label"]: item["count"] for item in body["depth_distribution"]["items"]}
    assert by_label["0-70"] == 2
    assert by_label["70-300"] == 2
    assert by_label[">=300"] == 2
    assert by_label["<0"] == 1


# --- comparison --------------------------------------------------------------------------


def test_comparison_without_baseline_events_is_nd_and_has_the_warning(api) -> None:
    api.add_event(version("R1", END - timedelta(hours=1)))

    body = stats(api, end=iso(END), baseline_year=2010)

    comparison = body["comparison"]
    assert comparison["ratio"] == "ND"
    assert comparison["baseline"]["events"] == 0 and comparison["baseline"]["daily_mean"] == 0
    assert comparison["recent"]["count"] == 1
    assert comparison["recent"]["end"] == int(END.timestamp() * 1000)
    assert comparison["recent"]["start"] == int((END - timedelta(hours=24)).timestamp() * 1000)
    assert comparison["warning"]
    assert set(comparison["filters_applied"]) == {"min_mag", "country_id", "exclude_synthetic"}


def test_baseline_mean_counts_the_days_without_events(api) -> None:
    api.add_event(version("R1", END - timedelta(hours=1)))
    for number in range(3):
        api.add_event(version(f"B{number}", datetime(2025, 3, 1 + number, 8, tzinfo=timezone.utc)))

    body = stats(api, end=iso(END))

    baseline = body["comparison"]["baseline"]
    assert baseline["year"] == 2025 and baseline["events"] == 3 and baseline["days"] == 365
    assert baseline["daily_mean"] == pytest.approx(3 / 365)
    assert body["comparison"]["ratio"] == pytest.approx(1 / (3 / 365))


def test_baseline_year_parameter_and_leap_year(api) -> None:
    api.add_event(version("L1", datetime(2024, 5, 1, 8, tzinfo=timezone.utc)))
    api.add_event(version("L2", datetime(2024, 5, 2, 8, tzinfo=timezone.utc)))

    baseline = stats(api, end=iso(END), baseline_year=2024)["comparison"]["baseline"]

    assert baseline["year"] == 2024 and baseline["days"] == 366 and baseline["events"] == 2
    assert baseline["daily_mean"] == pytest.approx(2 / 366)


def test_comparison_applies_the_filters_to_both_periods(api) -> None:
    api.add_event(version("R1", END - timedelta(hours=1), magnitude=5.0))
    api.add_event(version("R2", END - timedelta(hours=2), magnitude=2.0))
    api.add_event(version("B1", datetime(2025, 3, 1, tzinfo=timezone.utc), magnitude=5.0))
    api.add_event(version("B2", datetime(2025, 3, 2, tzinfo=timezone.utc), magnitude=2.0))

    comparison = stats(api, end=iso(END), min_mag="4")["comparison"]

    assert comparison["recent"]["count"] == 1
    assert comparison["baseline"]["events"] == 1


# --- revisions ---------------------------------------------------------------------------


def test_a_revision_moves_the_event_between_bins_and_countries(api) -> None:
    event_time = START + timedelta(hours=6)
    first = event_time + timedelta(minutes=5)
    api.add_event(version("REV", event_time, updated_at=first, magnitude=2.5, country_id="ESP"))

    before = stats(api, **day_params())
    assert {(i["from"], i["to"]): i["count"] for i in before["magnitude_distribution"]["items"]} == {(2, 3): 1}
    assert [i["country_id"] for i in before["by_country"]["items"]] == ["ESP"]

    api.add_event(
        version("REV", event_time, updated_at=first + timedelta(minutes=10), magnitude=4.5, country_id="JPN")
    )

    after = stats(api, **day_params())
    assert after["total"] == 1
    assert {(i["from"], i["to"]): i["count"] for i in after["magnitude_distribution"]["items"]} == {(4, 5): 1}
    assert [(i["country_id"], i["count"]) for i in after["by_country"]["items"]] == [("JPN", 1)]


def test_a_late_older_version_changes_nothing(api) -> None:
    event_time = START + timedelta(hours=6)
    current = event_time + timedelta(minutes=30)
    api.add_event(version("LATE", event_time, updated_at=current, magnitude=4.5, country_id="JPN"))
    before = stats(api, **day_params())

    api.add_event(
        version("LATE", event_time, updated_at=current - timedelta(minutes=20), magnitude=2.5, country_id="ESP")
    )

    after = stats(api, **day_params())
    assert after["total"] == 1
    assert after["magnitude_distribution"] == before["magnitude_distribution"]
    assert after["by_country"] == before["by_country"]


# --- replay ------------------------------------------------------------------------------


def test_replay_is_labelled_and_never_mixes_with_core(api) -> None:
    api.add_event(version("RP1", T2025, magnitude=4.0), schema="replay")
    api.add_event(version("RP2", T2025 + timedelta(hours=1), magnitude=3.0), schema="replay")
    api.add_event(version("LIVE1", datetime.now(timezone.utc) - timedelta(hours=1)))

    replay = stats(api, mode="replay")
    live = stats(api)

    assert replay["mode"] == "replay" and replay["metadata"]["mode"] == "replay"
    assert replay["metadata"]["label"] == LABEL
    assert "last_replayed_at" in replay["metadata"]
    assert replay["total"] == 2
    assert live["total"] == 1
    assert live["mode"] == "live" and "label" not in live["metadata"]
    assert "last_replayed_at" not in live["metadata"]


def test_exclude_synthetic_in_replay(api) -> None:
    api.add_event(version("REAL", T2025), schema="replay")
    api.add_event(version("synthetic-1", T2025 + timedelta(hours=1)), schema="replay")
    api.add_event(version("flagged", T2025 + timedelta(hours=2), quality_flags=["synthetic"]), schema="replay")

    included = stats(api, mode="replay")
    excluded = stats(api, mode="replay", exclude_synthetic="true")

    assert included["total"] == 3 and included["filters"]["exclude_synthetic"] is False
    assert excluded["total"] == 1 and excluded["filters"]["exclude_synthetic"] is True
    events = api.get("/api/eventos", mode="replay", exclude_synthetic="true").json()
    assert events["metadata"]["total"] == excluded["total"]


def test_live_never_counts_synthetic_events(api) -> None:
    api.add_event(version("synthetic-9", START + timedelta(hours=1)))
    api.add_event(version("REAL", START + timedelta(hours=2)))

    assert stats(api, **day_params())["total"] == 1


# --- indicated scope ---------------------------------------------------------------------


def test_the_result_states_period_filters_unit_and_scope(api) -> None:
    api.add_event(version("I1", START + timedelta(hours=1), magnitude=4.0, country_id="ESP"))

    body = stats(api, **day_params(), min_mag="3.5", country_id="ESP")

    assert body["scope"] == "complete" and body["unit"] == "events"
    assert body["period"] == {
        "start": int(START.timestamp() * 1000),
        "end": int(END.timestamp() * 1000),
        "default_applied": False,
    }
    assert body["filters"] == {"min_mag": 3.5, "country_id": "ESP", "exclude_synthetic": False}
    assert body["hourly"]["window"]
    assert isinstance(body["metadata"]["generated"], int)
    assert "unvalued" in body["magnitude_distribution"] and "unvalued" in body["depth_distribution"]


# --- not computed on the page ------------------------------------------------------------


def test_a_selection_above_max_features_is_complete_and_flags_the_map(api) -> None:
    api.set_max_features(3)
    for number in range(7):
        api.add_event(version(f"T{number}", START + timedelta(hours=1 + number), magnitude=3.0 + number * 0.1))

    body = stats(api, **day_params())

    assert body["map_truncated"] is True
    assert body["total"] == 7
    assert sum(i["count"] for i in body["hourly"]["items"]) == 7
    assert sum(i["count"] for i in body["magnitude_distribution"]["items"]) == 7
    assert sum(i["count"] for i in body["by_country"]["items"]) == 7


def test_a_selection_within_max_features_does_not_flag_the_map(api) -> None:
    api.set_max_features(10)
    for number in range(3):
        api.add_event(version(f"T{number}", START + timedelta(hours=1 + number)))

    assert stats(api, **day_params())["map_truncated"] is False


def test_statistics_have_no_pagination_and_reject_bad_parameters(api) -> None:
    assert api.get("/api/estadisticas", mode="x").status == 422
    assert api.get("/api/estadisticas", baseline_year="abc").status == 422
    ok = api.get("/api/estadisticas", **day_params(), limit=1, offset=5)
    assert ok.status == 200  # unknown parameters are ignored
