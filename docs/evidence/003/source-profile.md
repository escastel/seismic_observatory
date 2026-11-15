# Perfil de la fuente: respuestas reales de USGS (V10)

- Generado (UTC): 2026-11-15T19:04:15Z
- Orden: `docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m tests.analysis.source_profile`
- Datos: originales guardados en `core.raw_payload` (feed, un cuerpo por contenido distinto mientras dure su retención) y ficheros del catálogo en `data/usgs/catalog/`; consultas de `core.extraction`.
- «Usado» marca los campos que lee el sistema (enunciado §4.1). «Nulos» incluye valores `null` y campos ausentes en coordenadas; las longitudes de texto se dan en caracteres.

## Feed all_day.geojson (originales distintos guardados)

- Respuestas analizadas: 37; elementos: 6.960
- Ocurrencias entre 2026-11-14 11:35 y 2026-11-15 18:52 UTC
- Tipos de evento: `earthquake` 6.960
- Geometrías: `Point` 6.960; coordenadas por punto: 3: 6.960
- `updated − time` (minutos): mediana 3,5, percentil 95 739,3, máximo 1.208,3

| Campo | Usado | Unidad | Tipos observados | Presente | Nulos | Mín. | Máx. |
|---|---|---|---|---:|---:|---:|---:|
| `geometry.depth` | sí | km | decimal 5962, entero 998 | 6.960 | 0,0 % | -2,74 | 545,34 |
| `geometry.latitude` | sí | grados WGS84 | decimal 6923, entero 37 | 6.960 | 0,0 % | -44,36 | 67,25 |
| `geometry.longitude` | sí | grados WGS84 | decimal 6960 | 6.960 | 0,0 % | -178,34 | 179,81 |
| `geometry.type` | sí | texto | texto 6960 | 6.960 | 0,0 % | 5 | 5 |
| `id` | sí | texto | texto 6960 | 6.960 | 0,0 % | long. 10 | long. 13 |
| `properties.mag` | sí | adimensional | decimal 6589, entero 371 | 6.960 | 0,0 % | -0,02 | 5,50 |
| `properties.magType` | sí | texto | texto 6960 | 6.960 | 0,0 % | long. 2 | long. 3 |
| `properties.place` | sí | texto | texto 6960 | 6.960 | 0,0 % | long. 11 | long. 49 |
| `properties.time` | sí | ms Unix (UTC) | entero 6960 | 6.960 | 0,0 % | 2026-11-14 11:35 | 2026-11-15 18:52 |
| `properties.type` | sí | texto | texto 6960 | 6.960 | 0,0 % | long. 10 | long. 10 |
| `properties.updated` | sí | ms Unix (UTC) | entero 6960 | 6.960 | 0,0 % | 2026-11-14 11:39 | 2026-11-15 19:01 |
| `properties.alert` |  |  | null 6903, texto 57 | 6.960 | 99,2 % | long. 5 | long. 5 |
| `properties.cdi` |  |  | null 6492, decimal 318, entero 150 | 6.960 | 93,3 % | 1 | 4,60 |
| `properties.code` |  |  | texto 6960 | 6.960 | 0,0 % | long. 8 | long. 11 |
| `properties.detail` |  |  | texto 6960 | 6.960 | 0,0 % | long. 75 | long. 78 |
| `properties.dmin` |  |  | decimal 6474, entero 486 | 6.960 | 0,0 % | 0 | 13,67 |
| `properties.felt` |  |  | null 6492, entero 468 | 6.960 | 93,3 % | 0 | 372 |
| `properties.gap` |  |  | entero 6908, decimal 52 | 6.960 | 0,0 % | 16 | 325 |
| `properties.ids` |  |  | texto 6960 | 6.960 | 0,0 % | long. 12 | long. 26 |
| `properties.mmi` |  |  | null 6681, decimal 242, entero 37 | 6.960 | 96,0 % | 0 | 6,40 |
| `properties.net` |  |  | texto 6960 | 6.960 | 0,0 % | long. 2 | long. 2 |
| `properties.nst` |  |  | entero 6960 | 6.960 | 0,0 % | 4 | 168 |
| `properties.rms` |  |  | decimal 6906, entero 54 | 6.960 | 0,0 % | 0 | 1,66 |
| `properties.sig` |  |  | entero 6960 | 6.960 | 0,0 % | 0 | 471 |
| `properties.sources` |  |  | texto 6960 | 6.960 | 0,0 % | long. 4 | long. 7 |
| `properties.status` |  |  | texto 6960 | 6.960 | 0,0 % | long. 8 | long. 9 |
| `properties.title` |  |  | texto 6960 | 6.960 | 0,0 % | long. 19 | long. 57 |
| `properties.tsunami` |  |  | entero 6960 | 6.960 | 0,0 % | 0 | 0 |
| `properties.types` |  |  | texto 6960 | 6.960 | 0,0 % | long. 19 | long. 67 |
| `properties.tz` |  |  | null 6960 | 6.960 | 100,0 % | — | — |
| `properties.url` |  |  | texto 6960 | 6.960 | 0,0 % | long. 60 | long. 63 |

## Catálogo FDSN (ficheros de data/usgs/catalog)

- Respuestas analizadas: 24; elementos: 32.655
- Ocurrencias entre 2025-01-01 00:13 y 2026-11-14 22:23 UTC
- Tipos de evento: `earthquake` 32.655
- Geometrías: `Point` 32.655; coordenadas por punto: 3: 32.655
- `updated − time` (minutos): mediana 109.325,7, percentil 95 130.915,3, máximo 886.048,2

| Campo | Usado | Unidad | Tipos observados | Presente | Nulos | Mín. | Máx. |
|---|---|---|---|---:|---:|---:|---:|
| `geometry.depth` | sí | km | entero 17499, decimal 15156 | 32.655 | 0,0 % | 0,00 | 683,58 |
| `geometry.latitude` | sí | grados WGS84 | decimal 32652, entero 3 | 32.655 | 0,0 % | -84,49 | 87,08 |
| `geometry.longitude` | sí | grados WGS84 | decimal 32653, entero 2 | 32.655 | 0,0 % | -180,00 | 180,00 |
| `geometry.type` | sí | texto | texto 32655 | 32.655 | 0,0 % | 5 | 5 |
| `id` | sí | texto | texto 32655 | 32.655 | 0,0 % | long. 10 | long. 13 |
| `properties.mag` | sí | adimensional | decimal 30181, entero 2474 | 32.655 | 0,0 % | 0,21 | 8,80 |
| `properties.magType` | sí | texto | texto 32655 | 32.655 | 0,0 % | long. 2 | long. 3 |
| `properties.place` | sí | texto | texto 32654, null 1 | 32.655 | 0,0 % | long. 5 | long. 59 |
| `properties.time` | sí | ms Unix (UTC) | entero 32655 | 32.655 | 0,0 % | 2025-01-01 00:13 | 2026-11-14 22:23 |
| `properties.type` | sí | texto | texto 32655 | 32.655 | 0,0 % | long. 10 | long. 10 |
| `properties.updated` | sí | ms Unix (UTC) | entero 32655 | 32.655 | 0,0 % | 2025-03-17 21:33 | 2026-11-15 18:50 |
| `properties.alert` |  |  | null 31057, texto 1598 | 32.655 | 95,1 % | long. 3 | long. 6 |
| `properties.cdi` |  |  | null 29145, decimal 2552, entero 958 | 32.655 | 89,3 % | 0 | 9,10 |
| `properties.code` |  |  | texto 32655 | 32.655 | 0,0 % | long. 8 | long. 11 |
| `properties.detail` |  |  | texto 32655 | 32.655 | 0,0 % | long. 82 | long. 85 |
| `properties.dmin` |  |  | decimal 32542, null 70, entero 43 | 32.655 | 0,2 % | 0 | 59,03 |
| `properties.felt` |  |  | null 29145, entero 3510 | 32.655 | 89,3 % | 0 | 45.935 |
| `properties.gap` |  |  | entero 32580, null 69, decimal 6 | 32.655 | 0,2 % | 9 | 327 |
| `properties.ids` |  |  | texto 32655 | 32.655 | 0,0 % | long. 12 | long. 75 |
| `properties.mmi` |  |  | null 30350, decimal 2042, entero 263 | 32.655 | 92,9 % | 0 | 9,95 |
| `properties.net` |  |  | texto 32655 | 32.655 | 0,0 % | long. 2 | long. 2 |
| `properties.nst` |  |  | entero 32588, null 67 | 32.655 | 0,2 % | 0 | 566 |
| `properties.rms` |  |  | decimal 32395, entero 260 | 32.655 | 0,0 % | 0 | 1,81 |
| `properties.sig` |  |  | entero 32655 | 32.655 | 0,0 % | 1 | 2.910 |
| `properties.sources` |  |  | texto 32655 | 32.655 | 0,0 % | long. 4 | long. 27 |
| `properties.status` |  |  | texto 32655 | 32.655 | 0,0 % | long. 8 | long. 9 |
| `properties.title` |  |  | texto 32655 | 32.655 | 0,0 % | long. 8 | long. 67 |
| `properties.tsunami` |  |  | entero 32655 | 32.655 | 0,0 % | 0 | 1 |
| `properties.types` |  |  | texto 32655 | 32.655 | 0,0 % | long. 8 | long. 210 |
| `properties.tz` |  |  | null 32655 | 32.655 | 100,0 % | — | — |
| `properties.url` |  |  | texto 32655 | 32.655 | 0,0 % | long. 60 | long. 63 |

## Consultas registradas

| Fuente | Propósito | Resultado | Consultas | Primera | Última |
|---|---|---|---:|---|---|
| `usgs_catalog` | `gap_recovery` | `ok` | 3 | 2026-11-15 19:03 | 2026-11-15 19:03 |
| `usgs_catalog` | `historical_load` | `ok` | 70 | 2026-11-15 11:40 | 2026-11-15 11:52 |
| `usgs_feed` | `live` | `http_error` | 8 | 2026-11-15 18:57 | 2026-11-15 18:58 |
| `usgs_feed` | `live` | `invalid_json` | 4 | 2026-11-15 18:59 | 2026-11-15 19:00 |
| `usgs_feed` | `live` | `invalid_structure` | 4 | 2026-11-15 19:00 | 2026-11-15 19:01 |
| `usgs_feed` | `live` | `not_modified` | 3 | 2026-11-15 18:37 | 2026-11-15 18:42 |
| `usgs_feed` | `live` | `ok` | 94 | 2026-11-15 11:31 | 2026-11-15 19:03 |
| `usgs_feed` | `live` | `timeout` | 4 | 2026-11-15 18:59 | 2026-11-15 18:59 |

### Latencia de las consultas (`duration_ms`, reintentos incluidos)

| Fuente | Tipo | Consultas | Mediana (ms) | Percentil 95 (ms) | Máximo (ms) |
|---|---|---:|---:|---:|---:|
| `usgs_catalog` | count | 49 | 473 | 1.153 | 1.428 |
| `usgs_catalog` | query | 24 | 871 | 1.057 | 1.068 |
| `usgs_feed` | feed | 117 | 102 | 5.005 | 7.012 |

### Frecuencia real de cambio del feed

- 97 consultas correctas en 5 horas distintas; 37 contenidos distintos (huella de la lista de eventos).
- Contenidos distintos por hora: mediana 3, mínimo 1, máximo 18.
- Respuestas «sin cambios» (304): 3.

### Retraso de ingesta de los eventos del feed (`first_ingested_at − event_time`)

- 9 eventos ocurridos con el productor funcionando (hubo una consulta correcta en los 2 minutos anteriores); mediana 3,2 min; percentil 95 4,1 min. Incluye el retraso con que USGS publica el evento, el minuto entre consultas y el paso por Kafka y el consumidor. Se excluyen los eventos que ya estaban en la ventana de 24 h al arrancar y los ocurridos durante una parada: su retraso mide la parada, no la ingesta.

### Errores registrados

| Fuente | Resultado | HTTP | Detalle | Veces |
|---|---|---:|---|---:|
| `usgs_feed` | `http_error` | 429 | HTTP 429: Too Many Requests (Retry-After 5 s) | 4 |
| `usgs_feed` | `invalid_structure` | 200 | expected type FeatureCollection, got 'Feature' | 4 |
| `usgs_feed` | `timeout` | — | timeout after 3 s: HTTPConnectionPool(host='usgs-stub', port=8080): Read timed out. (read timeout=3) | 4 |
| `usgs_feed` | `http_error` | 503 | HTTP 503: Service Unavailable | 4 |
| `usgs_feed` | `invalid_json` | 200 | response is not JSON: Expecting value: line 1 column 1 (char 0) | 4 |
