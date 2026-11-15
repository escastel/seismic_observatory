# Medición de índices del modelo (V11)

- Fecha (UTC): 2026-11-15T00:41:37Z
- Servidor: PostgreSQL 16.4 (Debian 16.4-1.pgdg120+2) on x86_64-pc-linux-gnu, compiled by gcc (Debian 12.2.0-14) 12.2.0, 64-bit; shared_buffers 128MB, work_mem 4MB
- Cliente: Linux 6.18.58.1-microsoft-standard-WSL2 x86_64, Python 3.11.10; 12 CPU y 7.6 GiB visibles en el contenedor
- Equipo: Windows 11 Pro for Workstations 10.0.26200, Docker Desktop 29.1.3 (motor con 12 CPU y 7.6 GiB)
- Orden: `docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m tests.benchmark.index_benchmark`

## Procedimiento

1. Se crea el esquema `bench` con la misma plantilla que `core` y `replay` (`db/sql/040_event_tables.sql`), más una copia de `core.extraction`.
2. Para cada tamaño (10.000, 100.000 y 1.000.000 de eventos) se cargan datos sintéticos: eventos repartidos de forma uniforme en 2025 e insertados en orden temporal; magnitudes de Gutenberg-Richter con b = 1 desde M1 y tope en M8 (cada unidad, diez veces menos eventos; ≈0,1 % con M ≥ 4); un 30 % sin país y el resto repartido entre los 177 países; una versión por evento y una segunda para el 5 %; una extracción por minuto, con un 5 % del catálogo y un 3 % fallidas. Después, `VACUUM (ANALYZE)`.
3. Cada consulta se ejecuta con `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`: una ejecución de calentamiento y 5 medidas. Se anota la mediana del tiempo de ejecución y los búferes compartidos (leídos más en caché) del nodo superior de la ejecución mediana.
4. Primero sin índices secundarios (solo claves primarias); después se crea cada candidato, se analiza la tabla, se mide y se elimina. Para las versiones de un evento, cuyo índice es la propia clave primaria, se compara contra una copia de `event_version` sin clave.
5. Criterio (research.md R11): se conserva un índice si alguna de sus consultas es al menos 2 veces más rápida en mediana con 1.000.000 de filas. El BRIN solo se mide.
6. El esquema `bench` se elimina al terminar, también si la medición falla.

## Decisión con 1.000.000 de filas

| Índice | Consulta | Sin índice / con índice | Decisión |
|---|---|---|---|
| `event_time` | `last_24h`, `month_by_hour` | `last_24h` ×125,8; `month_by_hour` ×2,4 | conservar |
| `country_event_time` | `country_interval` | `country_interval` ×199,0 | conservar |
| `magnitude_event_time` | `min_magnitude_year` | `min_magnitude_year` ×40,2 | conservar |
| `brin_event_time` | `last_24h`, `month_by_hour` | `last_24h` ×34,3; `month_by_hour` ×2,0 | medido (alternativa a event_time) |
| `extraction_last_ok` | `last_ingestion` | `last_ingestion` ×4935,9 | conservar |
| `event_version_pkey` | `versions_of_event` | `versions_of_event` ×4858,9 | obligatorio (clave primaria) |

## Mediciones

### `last_24h`: Eventos de las últimas 24 h (mapa por defecto)

| Filas | Índice | Mediana (ms) | Búferes | Tamaño del índice | Plan |
|---:|---|---:|---:|---:|---|
| 10.000 | sin índice secundario | 0,462 | 200 | — | Sort → Seq Scan |
| 10.000 | `event_time` | 0,013 | 4 | 0,23 MiB | Index Scan using ix_bench_event_time |
| 10.000 | `brin_event_time` | 0,244 | 74 | 0,02 MiB | Sort → Bitmap Heap Scan → Bitmap Index Scan using ix_bench_brin_event_time |
| 100.000 | sin índice secundario | 4,746 | 2.000 | — | Sort → Seq Scan |
| 100.000 | `event_time` | 0,059 | 11 | 2,16 MiB | Index Scan using ix_bench_event_time |
| 100.000 | `brin_event_time` | 0,334 | 82 | 0,02 MiB | Sort → Bitmap Heap Scan → Bitmap Index Scan using ix_bench_brin_event_time |
| 1.000.000 | sin índice secundario | 53,582 | 20.073 | — | Gather Merge → Sort → Seq Scan |
| 1.000.000 | `event_time` | 0,426 | 76 | 21,45 MiB | Index Scan using ix_bench_event_time |
| 1.000.000 | `brin_event_time` | 1,561 | 161 | 0,02 MiB | Sort → Bitmap Heap Scan → Bitmap Index Scan using ix_bench_brin_event_time |

```sql
SELECT event_id, event_time, magnitude, longitude, latitude FROM bench.event_current WHERE event_time >= timestamptz '2025-12-31 00:00+00' AND event_time < timestamptz '2026-01-01 00:00+00' ORDER BY event_time DESC
```

### `month_by_hour`: Un mes agrupado por hora UTC (serie temporal)

| Filas | Índice | Mediana (ms) | Búferes | Tamaño del índice | Plan |
|---:|---|---:|---:|---:|---|
| 10.000 | sin índice secundario | 0,791 | 200 | — | Aggregate → Sort → Seq Scan |
| 10.000 | `event_time` | 0,369 | 5 | 0,23 MiB | Aggregate → Sort → Index Only Scan using ix_bench_event_time |
| 10.000 | `brin_event_time` | 0,757 | 130 | 0,02 MiB | Aggregate → Sort → Bitmap Heap Scan → Bitmap Index Scan using ix_bench_brin_event_time |
| 100.000 | sin índice secundario | 6,587 | 2.000 | — | Aggregate → Sort → Seq Scan |
| 100.000 | `event_time` | 2,437 | 25 | 2,16 MiB | Aggregate → Sort → Index Only Scan using ix_bench_event_time |
| 100.000 | `brin_event_time` | 3,130 | 258 | 0,02 MiB | Aggregate → Sort → Bitmap Heap Scan → Bitmap Index Scan using ix_bench_brin_event_time |
| 1.000.000 | sin índice secundario | 51,318 | 20.071 | — | Aggregate → Gather Merge → Sort → Seq Scan |
| 1.000.000 | `event_time` | 21,803 | 228 | 21,45 MiB | Aggregate → Sort → Index Only Scan using ix_bench_event_time |
| 1.000.000 | `brin_event_time` | 25,550 | 1.794 | 0,02 MiB | Aggregate → Sort → Bitmap Heap Scan → Bitmap Index Scan using ix_bench_brin_event_time |

```sql
SELECT date_trunc('hour', event_time AT TIME ZONE 'UTC') AS hour, count(*) FROM bench.event_current WHERE event_time >= timestamptz '2025-06-01 00:00+00' AND event_time < timestamptz '2025-07-01 00:00+00' GROUP BY 1 ORDER BY 1
```

### `country_interval`: Un país en un mes (filtro por país)

| Filas | Índice | Mediana (ms) | Búferes | Tamaño del índice | Plan |
|---:|---|---:|---:|---:|---|
| 10.000 | sin índice secundario | 0,688 | 200 | — | Sort → Seq Scan |
| 10.000 | `country_event_time` | 0,021 | 4 | 0,32 MiB | Sort → Bitmap Heap Scan → Bitmap Index Scan using ix_bench_country_event_time |
| 100.000 | sin índice secundario | 7,999 | 2.000 | — | Sort → Seq Scan |
| 100.000 | `country_event_time` | 0,042 | 33 | 3,03 MiB | Sort → Bitmap Heap Scan → Bitmap Index Scan using ix_bench_country_event_time |
| 1.000.000 | sin índice secundario | 55,125 | 20.073 | — | Gather Merge → Sort → Seq Scan |
| 1.000.000 | `country_event_time` | 0,277 | 324 | 30,10 MiB | Sort → Bitmap Heap Scan → Bitmap Index Scan using ix_bench_country_event_time |

```sql
SELECT event_id, event_time, magnitude FROM bench.event_current WHERE country_id = 'JPN' AND event_time >= timestamptz '2025-03-01 00:00+00' AND event_time < timestamptz '2025-04-01 00:00+00' ORDER BY event_time DESC
```

### `min_magnitude_year`: Magnitud mínima 4 sobre el año completo

| Filas | Índice | Mediana (ms) | Búferes | Tamaño del índice | Plan |
|---:|---|---:|---:|---:|---|
| 10.000 | sin índice secundario | 0,482 | 200 | — | Sort → Seq Scan |
| 10.000 | `magnitude_event_time` | 0,025 | 11 | 0,32 MiB | Sort → Bitmap Heap Scan → Bitmap Index Scan using ix_bench_magnitude_event_time |
| 100.000 | sin índice secundario | 6,173 | 2.000 | — | Sort → Seq Scan |
| 100.000 | `magnitude_event_time` | 0,104 | 89 | 3,03 MiB | Sort → Bitmap Heap Scan → Bitmap Index Scan using ix_bench_magnitude_event_time |
| 1.000.000 | sin índice secundario | 40,354 | 20.073 | — | Gather Merge → Sort → Seq Scan |
| 1.000.000 | `magnitude_event_time` | 1,004 | 988 | 30,10 MiB | Sort → Bitmap Heap Scan → Bitmap Index Scan using ix_bench_magnitude_event_time |

```sql
SELECT event_id, event_time, magnitude FROM bench.event_current WHERE magnitude >= 4 AND event_time >= timestamptz '2025-01-01 00:00+00' AND event_time < timestamptz '2026-01-01 00:00+00' ORDER BY event_time DESC
```

### `versions_of_event`: Versiones de un event_id (historial)

| Filas | Índice | Mediana (ms) | Búferes | Tamaño del índice | Plan |
|---:|---|---:|---:|---:|---|
| 10.000 | copia sin clave primaria | 0,636 | 640 | — | Sort → Seq Scan |
| 10.000 | `event_version_pkey` | 0,012 | 3 | 0,72 MiB | Index Scan using event_version_pkey |
| 100.000 | copia sin clave primaria | 13,666 | 6.208 | — | Sort → Seq Scan |
| 100.000 | `event_version_pkey` | 0,015 | 4 | 7,07 MiB | Index Scan using event_version_pkey |
| 1.000.000 | copia sin clave primaria | 68,024 | 61.824 | — | Sort → Gather → Seq Scan |
| 1.000.000 | `event_version_pkey` | 0,014 | 4 | 70,59 MiB | Index Scan using event_version_pkey |

```sql
SELECT updated_at, magnitude, payload FROM bench.event_version WHERE event_id = %(event_id)s ORDER BY updated_at
```

### `last_ingestion`: Última consulta correcta al feed (last_ingestion)

| Filas | Índice | Mediana (ms) | Búferes | Tamaño del índice | Plan |
|---:|---|---:|---:|---:|---|
| 10.000 | sin índice secundario | 1,604 | 197 | — | Aggregate → Seq Scan |
| 10.000 | `extraction_last_ok` | 0,013 | 3 | 0,22 MiB | Result → Limit → Index Only Scan using ix_bench_extraction_last_ok |
| 100.000 | sin índice secundario | 16,982 | 1.961 | — | Aggregate → Seq Scan |
| 100.000 | `extraction_last_ok` | 0,014 | 3 | 1,98 MiB | Result → Limit → Index Only Scan using ix_bench_extraction_last_ok |
| 1.000.000 | sin índice secundario | 78,975 | 19.608 | — | Aggregate → Gather → Seq Scan |
| 1.000.000 | `extraction_last_ok` | 0,016 | 4 | 19,75 MiB | Result → Limit → Index Only Scan using ix_bench_extraction_last_ok |

```sql
SELECT max(requested_at) FROM bench.extraction WHERE source = 'usgs_feed' AND outcome IN ('ok', 'not_modified')
```

