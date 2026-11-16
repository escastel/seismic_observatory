from datetime import datetime, timedelta, timezone

import pytest

from api.app.filters import ParameterError, build_where, parse_filters

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
START = datetime(2025, 3, 1, tzinfo=timezone.utc)
END = datetime(2025, 3, 2, tzinfo=timezone.utc)


def where(**kwargs):
    return build_where(parse_filters(**kwargs), NOW)


def fails(param, **kwargs):
    with pytest.raises(ParameterError) as info:
        parse_filters(**kwargs)
    assert info.value.param == param


def test_start_without_timezone_is_rejected():
    fails("start", start=datetime(2025, 3, 1))


def test_end_without_timezone_is_rejected():
    fails("end", end=datetime(2025, 3, 1))


def test_start_not_before_end_is_rejected():
    fails("start", start=END, end=START)
    fails("start", start=START, end=START)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_min_mag_is_rejected(value):
    fails("min_mag", min_mag=value)


def test_text_min_mag_is_rejected():
    with pytest.raises((ParameterError, TypeError)):
        parse_filters(min_mag="abc")  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ["", "ES P", "ES-P", "E;S", "'; DROP", "ABCDEFGHI"])
def test_invalid_country_id_is_rejected(value):
    fails("country_id", country_id=value)


def test_valid_country_id_is_accepted():
    assert parse_filters(country_id="ESP").country_id == "ESP"


def test_unknown_mode_is_rejected():
    fails("mode", mode="history")


def test_live_without_start_applies_24h_window():
    w = where(mode="live")
    assert w.default_applied is True
    assert w.period_start == NOW - timedelta(hours=24)
    assert w.period_end is None
    assert NOW - timedelta(hours=24) in w.values


def test_live_window_is_relative_to_end():
    w = where(mode="live", end=END)
    assert w.period_start == END - timedelta(hours=24)
    assert w.period_end == END


def test_live_with_start_has_no_default_window():
    w = where(mode="live", start=START)
    assert w.default_applied is False
    assert w.period_start == START


def test_replay_never_applies_default_window():
    w = where(mode="replay")
    assert w.default_applied is False
    assert w.period_start is None
    assert w.values == []
    assert w.sql == ""


def test_map_and_statistics_get_same_where_and_values():
    kwargs = dict(mode="live", start=START, end=END, min_mag=4.5, country_id="ESP")
    first = build_where(parse_filters(**kwargs), NOW)
    second = build_where(parse_filters(**kwargs), NOW)
    assert first == second


def test_without_min_mag_drops_only_the_magnitude_condition():
    filters = parse_filters(mode="live", start=START, end=END, min_mag=4.5, country_id="ESP")
    full = build_where(filters, NOW)
    partial = build_where(filters, NOW, with_min_mag=False)
    assert 4.5 in full.values
    assert 4.5 not in partial.values
    assert "magnitude" in full.sql
    assert "magnitude" not in partial.sql
    assert "ESP" in partial.values


def test_live_always_excludes_synthetic():
    plain = where(mode="live", start=START)
    flagged = where(mode="live", start=START, exclude_synthetic=True)
    assert "synthetic" in plain.sql
    assert plain.sql == flagged.sql
    assert plain.values == flagged.values


def test_replay_excludes_synthetic_only_when_asked():
    assert "synthetic" not in where(mode="replay").sql
    assert "synthetic" in where(mode="replay", exclude_synthetic=True).sql


def test_values_are_bound_not_interpolated():
    w = where(mode="live", start=START, end=END, min_mag=4.5, country_id="ESP")
    for value in w.values:
        assert str(value) not in w.sql
    assert "ESP" not in w.sql
    assert "4.5" not in w.sql
    assert "2025" not in w.sql
    assert len(w.values) == 4
    for n in range(1, len(w.values) + 1):
        assert f"${n}" in w.sql
