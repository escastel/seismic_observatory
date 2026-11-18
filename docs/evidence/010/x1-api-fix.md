# X1. Corrección de `GET /api/estadisticas` sin eventos (T010–T012)

**Esperado**: con cualquier filtro sin eventos, `period.start` y `period.end` son números (contrato de la 006); en vivo con el periodo por defecto hay ventanas a cero; en reproducción sin eventos ni inicio, `start == end` y sin ventanas; con eventos nada cambia.

**Antes del arreglo** (pruebas escritas primero): `3 failed, 23 passed` (`period.end` era `null`).
**Después** (`api/app/stats.py::hourly_counts`, API reconstruida con `docker compose up --build -d api`):
`docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m pytest tests/query_api/test_statistics.py -q` → `26 passed`.

## Cambios justificados
- `api/app/stats.py`: si no hay `end` ni eventos, `end = now`; si no hay `start`, `start = end`; sin ventanas si `start >= end`. El contrato no cambia: se hace cumplir.
- `frontend/src/app/data/observatory.service.ts`: un fallo de estadísticas que es solo una respuesta no válida (422 o `invalid_response`) ya no descarta el refresco: se muestran los eventos del filtro nuevo con `statistics = null` y `statsFailure`. La red caída o el 503 siguen conservando la última lectura. La decisión es la función pura `lib/stats-tolerance.ts`.
