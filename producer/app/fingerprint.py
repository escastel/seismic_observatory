"""Content fingerprints of what USGS returned (spec 003, research R3).

- Feed responses: SHA-256 of the features list in canonical JSON. metadata
  (generated, count...) changes on every regeneration even when the events do
  not, so it is left out on purpose.
- Unreadable bodies and catalog files: SHA-256 of the bytes, so any standard
  tool (sha256sum) can check that a file has not changed.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

CHUNK = 1 << 20


def canonical_json(value: Any) -> bytes:
    """Sorted keys, no spaces, UTF-8: the same data always gives the same bytes."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def features_fingerprint(features: Sequence[Any]) -> str:
    return hashlib.sha256(canonical_json(list(features))).hexdigest()


def bytes_fingerprint(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_fingerprint(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()
