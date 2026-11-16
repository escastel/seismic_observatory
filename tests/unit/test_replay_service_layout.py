"""The replay package imports the way the producer image runs it (``app`` and ``common`` only).

The unit tests import ``producer.app.replay``; the container has no ``producer`` package. A plain
absolute import of ``producer.app...`` passes the tests and crashes the service, so the package is
copied to a directory laid out like the image (``/app/app`` and ``/app/common``) and imported in a
fresh interpreter where ``producer`` cannot be found.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MODULES = ["cli", "selection", "runner", "isolation", "control", "pacing", "message", "synthetic"]
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")


@pytest.fixture(scope="module")
def image_layout(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("image")
    shutil.copytree(REPO / "producer" / "app", root / "app", ignore=IGNORE)
    shutil.copytree(REPO / "common", root / "common", ignore=IGNORE)
    return root


@pytest.mark.parametrize("module", MODULES)
def test_module_imports_with_the_service_layout(image_layout: Path, module: str) -> None:
    pytest.importorskip("aiokafka")
    code = f"import sys; sys.path[:0] = [{str(image_layout)!r}]; import app.replay.{module}"
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, cwd=image_layout, check=False)
    assert result.returncode == 0, result.stderr
