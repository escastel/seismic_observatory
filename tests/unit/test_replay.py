from producer.app.replay import _resolve_replay_path


def test_replay_maps_windows_git_bash_path_to_docker_mount(monkeypatch, tmp_path) -> None:
    mounted = tmp_path / "historical_1900.jsonl"
    mounted.write_text("{}\n", encoding="utf-8")

    class FakePath:
        def __init__(self, value):
            self.value = str(value)
            self.path = mounted if self.value.startswith("/data/seeds/") else tmp_path / "missing"

        @property
        def name(self):
            return self.value.replace("\\", "/").rsplit("/", 1)[-1]

        def is_file(self):
            return self.path.is_file()

        def __truediv__(self, value):
            return FakePath(f"/data/seeds/{value}")

        def __str__(self):
            return str(self.path)

    monkeypatch.setattr(
        "producer.app.replay.Path",
        FakePath,
    )
    assert _resolve_replay_path("C:/Program Files/Git/data/seeds/historical_1900.jsonl").path == mounted
