"""Heartbeat semantics of common.health (contracts/runtime.md)."""

from __future__ import annotations

from common.health import Heartbeat, is_fresh, main

INTERVAL = 60


def test_recent_heartbeat_is_healthy(tmp_path) -> None:
    path = tmp_path / "heartbeat"
    Heartbeat(path).beat(now=1_000.0)
    assert is_fresh(3 * INTERVAL, path, now=1_000.0 + 2 * INTERVAL)
    assert is_fresh(3 * INTERVAL, path, now=1_000.0 + 3 * INTERVAL)


def test_heartbeat_older_than_three_intervals_is_unhealthy(tmp_path) -> None:
    path = tmp_path / "heartbeat"
    Heartbeat(path).beat(now=1_000.0)
    assert not is_fresh(3 * INTERVAL, path, now=1_000.0 + 3 * INTERVAL + 1)


def test_missing_or_damaged_heartbeat_is_unhealthy(tmp_path) -> None:
    assert not is_fresh(3 * INTERVAL, tmp_path / "never-written")
    damaged = tmp_path / "damaged"
    damaged.write_text("not a time", encoding="utf-8")
    assert not is_fresh(3 * INTERVAL, damaged)


def test_command_exit_codes(tmp_path, capsys) -> None:
    path = tmp_path / "heartbeat"
    assert main(["--max-age", "180", "--path", str(path)]) == 1
    Heartbeat(path).beat()
    assert main(["--max-age", "180", "--path", str(path)]) == 0
    assert "healthy" in capsys.readouterr().out
