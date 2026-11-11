from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_required_project_artifacts_exist() -> None:
    required = (
        "compose.yaml",
        "docs/calidad.md",
        "docs/evaluacion-financiera.md",
        "db/seeds/README.md",
        "tests/integration/benchmark_scaling.py",
    )
    assert all((ROOT / path).is_file() for path in required)


def test_prohibited_technologies_are_not_declared() -> None:
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8").lower()
    assert not any(term in text for term in ("spark", "flink", "kubernetes", "streamlit"))
