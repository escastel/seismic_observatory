"""Compara el tiempo de ocurrencia y el de actualización de replay.event_current con los GeoJSON originales.

Uso (desde la raíz del repositorio, con el stack levantado):

    python3 docs/evidence/005/check_original_times.py data/usgs/catalog replay_times.csv

`replay_times.csv` se genera con
    psql -At -F, -c "SELECT event_id, (extract(epoch FROM event_time)*1000)::bigint,
                            (extract(epoch FROM updated_at)*1000)::bigint FROM replay.event_current"
Imprime cuántos eventos coinciden y cuántos difieren; código de salida 1 si hay alguna diferencia.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def originals(catalog: Path) -> dict[str, tuple[int, int]]:
    latest: dict[str, tuple[int, int]] = {}
    for path in sorted(catalog.glob("*.geojson")):
        for feature in json.loads(path.read_text(encoding="utf-8"))["features"]:
            props = feature["properties"]
            current = latest.get(feature["id"])
            if current is None or props["updated"] > current[1]:
                latest[feature["id"]] = (props["time"], props["updated"])
    return latest


def main(catalog: str, csv_path: str) -> int:
    source = originals(Path(catalog))
    same = different = missing = 0
    with open(csv_path, encoding="utf-8", newline="") as handle:
        for event_id, time_ms, updated_ms in csv.reader(handle):
            original = source.get(event_id)
            if original is None:
                missing += 1
            elif original == (int(time_ms), int(updated_ms)):
                same += 1
            else:
                different += 1
    print(f"coinciden: {same}; difieren: {different}; sin original: {missing}")
    return 0 if different == 0 and missing == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
