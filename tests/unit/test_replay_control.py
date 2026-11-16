import threading

import pytest

from producer.app.replay.control import (
    consume_control,
    read_control,
    read_status,
    write_control,
    write_status,
)


@pytest.mark.parametrize("command", ["pause", "resume", "stop"])
def test_control_round_trip(tmp_path, command):
    write_control(tmp_path, command)
    order = read_control(tmp_path)
    assert order["command"] == command
    assert order["requested_at"].endswith("+00:00")


def test_read_control_without_file(tmp_path):
    assert read_control(tmp_path) is None


def test_consume_is_single_use(tmp_path):
    write_control(tmp_path, "pause")
    assert consume_control(tmp_path)["command"] == "pause"
    assert consume_control(tmp_path) is None
    assert read_control(tmp_path) is None


def test_invalid_command(tmp_path):
    with pytest.raises(ValueError):
        write_control(tmp_path, "explode")
    assert read_control(tmp_path) is None


def test_missing_directory_is_created(tmp_path):
    target = tmp_path / "a" / "replay"
    write_control(target, "stop")
    write_status(target, run="r1", state="running")
    assert read_control(target)["command"] == "stop"
    assert read_status(target)["run"] == "r1"


def test_status_round_trip_and_merge(tmp_path):
    assert read_status(tmp_path) is None
    write_status(tmp_path, run="r1", state="running", total=10, sent=0, error=None)
    write_status(tmp_path, sent=4, remaining=6)
    status = read_status(tmp_path)
    assert status["run"] == "r1"
    assert status["sent"] == 4 and status["remaining"] == 6 and status["total"] == 10
    assert status["updated_at"]


def test_invalid_state_and_field(tmp_path):
    with pytest.raises(ValueError):
        write_status(tmp_path, state="flying")
    with pytest.raises(ValueError):
        write_status(tmp_path, bogus=1)


def test_files_use_lf(tmp_path):
    write_status(tmp_path, run="r1", state="running")
    assert b"\r" not in (tmp_path / "status.json").read_bytes()


def test_status_never_partial_while_writing(tmp_path):
    write_status(tmp_path, run="r1", state="running", sent=0)
    stop = threading.Event()
    errors = []

    def writer():
        i = 0
        while not stop.is_set():
            write_status(tmp_path, sent=i)
            i += 1

    thread = threading.Thread(target=writer)
    thread.start()
    try:
        for _ in range(300):
            try:
                status = read_status(tmp_path)
            except Exception as exc:  # JSON a medias o error de lectura
                errors.append(exc)
                break
            assert status is not None
    finally:
        stop.set()
        thread.join()
    assert not errors
