import pytest

from api.app.stats import compare


def test_leap_year_has_366_days():
    assert compare(0, 10, 2024)["baseline"]["days"] == 366


def test_common_year_has_365_days():
    assert compare(0, 10, 2025)["baseline"]["days"] == 365


def test_zero_baseline_gives_nd():
    result = compare(5, 0, 2025)
    assert result["ratio"] == "ND"
    assert result["baseline"]["daily_mean"] == 0


def test_denominator_counts_days_without_events():
    result = compare(1, 3, 2025)
    assert result["baseline"]["daily_mean"] == pytest.approx(3 / 365)
    assert result["baseline"]["events"] == 3
    assert result["baseline"]["year"] == 2025


def test_ratio_is_recent_over_daily_mean():
    assert compare(6, 365, 2025)["ratio"] == pytest.approx(6.0)
    assert compare(0, 365, 2025)["ratio"] == 0


def test_warning_always_present_and_extended_for_replay():
    plain = compare(1, 1, 2025)
    replay = compare(1, 1, 2025, anchor_is_data=True)
    assert "incompleto" in plain["warning"]
    assert replay["warning"].startswith(plain["warning"])
    assert len(replay["warning"]) > len(plain["warning"])
    assert plain["filters_applied"] == ["min_mag", "country_id", "exclude_synthetic"]
