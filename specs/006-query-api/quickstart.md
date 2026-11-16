# Quickstart de verificación: API de consulta (spec 006)

Cada escenario se ejecuta con el sistema levantado (skill `verify-stack`) y deja su resultado
esperado y observado en `docs/evidence/006/`. Contrato en [contracts/api.md](contracts/api.md).

## Requisitos

- `.env` derivado de `.env.example`; `docker compose up --build -d` con los cinco servicios sanos.
- Base con datos: catálogo 2025 cargado en `core` (spec 003) y, para V9–V10, la selección de la
  spec 005 disponible. En Git Bash, anteponer `MSYS_NO_PATHCONV=1` a las órdenes con rutas de
  contenedor.
- En los ejemplos, `API=http://127.0.0.1:8000/api`.

## Escenarios

| Id | Qué comprueba | Cómo | Esperado |
|---|---|---|---|
| V1 | Forma del contrato | `GET $API/eventos` | 200, `FeatureCollection`, `metadata` con `generated`, `last_ingestion`, `mode: live`, `count`, `total`, `truncated`; coordenadas `[lon, lat, prof]`; tiempos enteros; ningún NaN |
| V2 | Filtros | `start`, `end` (exclusivo en el instante exacto), `min_mag=4`, `country_id` y combinados | cada resultado cumple todos; evento en `end` no entra; evento en `start` sí |
| V3 | Evento nuevo y repetición | inyectar un mensaje válido; repetirlo | aparece una vez; `total` no sube al repetir |
| V4 | Revisión y versión antigua | enviar versión posterior y luego una anterior | `updated` y datos nuevos; agregaciones cambian; la antigua no cambia nada |
| V5 | Magnitud nula | evento con magnitud nula, con y sin `min_mag` | sin filtro: `mag: null`; con filtro: fuera y `null_magnitude.excluded: true` |
| V6 | Geometría | mensaje con coordenadas inválidas | ningún `Feature` sin punto; `quarantined.invalid_geometry` +1 |
| V7 | Sin país | evento marítimo | aparece con `country_id: null`; en estadísticas bajo «Sin país asignado»; no filtrado por `country_id` |
| V8 | Truncado y paginación | periodo con más de 1.000 eventos; recorrer con `next_offset` | `truncated: true`, `total` completo; cada evento una sola vez |
| V9 | Reproducción | `?mode=replay` tras una reproducción | `metadata.mode: replay`, `label: REPRODUCCIÓN`, `replayed_at` en cada `Feature`, sin ventana de 24 h; `last_ingestion` real |
| V10 | Aislamiento | conteos `live` antes y después de reproducir | idénticos; el mismo id en ambos modos con valores propios; sintéticos excluibles |
| V11 | Estadísticas | por hora, país, distribuciones y comparación | total igual al del mapa (batería de filtros); horas vacías con 0; `ND` si la media es 0; aviso presente; nulos aparte |
| V12 | Salud y base caída | `GET $API/salud`; `docker compose stop postgres`; eventos, estadísticas, salud; `start` | salud 200 `degraded`; eventos y estadísticas 503 JSON; tras reiniciar, vuelve a `ok` sin reiniciar la API |
| V13 | Validación y acceso | `mode=x`, `start` sin zona, `start>=end`, `min_mag=abc`; preflight desde un origen permitido y otro no | 422 con parámetro y motivo; cabeceras CORS solo al permitido, sin `Allow-Credentials` |
| V14 | Superficie | listar rutas y métodos; `POST /api/eventos`; `/api/eventos?format=json` | solo las del contrato; 405 en escritura; respuesta siempre `FeatureCollection` |
| V15 | Planes e índices | `EXPLAIN (ANALYZE, BUFFERS)` de las consultas de R9 | usan los índices de la spec 002 (sin escaneo secuencial en los tamaños medidos) |
| V16 | Latencia | `python3 tests/benchmark/api_latency.py` en el contenedor `tests` | tres tamaños, mediana/p95/máximo, equipo y procedimiento; SC-008 |

## Comprobaciones de la suite

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests pytest tests/unit tests/contract -v
# La suite que usa la base (tests/db y tests/query_api) la ejecuta solo la sesión principal, una vez:
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests pytest tests/query_api -v
```
