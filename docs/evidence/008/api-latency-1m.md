# V6 · Latencia de la API con 1.000.000 de filas sintéticas (T014, T015)

**Fecha**: 2026-11-17 14:57–15:03 UTC · **Rama**: `008-analysis-costs-deliverables` · **Resultado**: SUPERADA (mediana ≤ 2.000 ms en todas
las consultas, 0 fallos) · **DATOS SINTÉTICOS**: esquema `bench`, ni `core` ni `replay`.

## Equipo y procedimiento

- **Equipo**: Windows 11 Pro for Workstations, Intel Core i5-11400H (2,70 GHz, 12 hilos lógicos), 15,7 GB de RAM (7,6 GiB visibles para Docker/WSL2),
  Docker Desktop 29.1.3, PostgreSQL 16.4 (`shared_buffers` 128 MB, `work_mem` 4 MB). Productor, consumidor y Kafka seguían activos.
- **Orden** (sin y con índices secundarios):

  ```bash
  docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -u -m tests.benchmark.api_latency_scale
  docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -u -m tests.benchmark.api_latency_scale --indexes
  ```

- **Método**: se cargan 1.000.000 de eventos sintéticos en `bench` (90–100 s), se concede lectura al rol de la API, se importa la aplicación
  FastAPI **en proceso** (sin red ni túnel, como la medición de la 006) y se sustituye **en memoria** `SEARCH_PATHS["replay"]` por
  `"bench, core"`: el modo `replay` de la API lee `bench`. `api/` no se modifica (decisión R5 de [00-environment.md](00-environment.md)). 5 peticiones de calentamiento y 30 medidas
  secuenciales por consulta. Los datos sintéticos tienen eventos uniformes en 2025, magnitudes de Gutenberg-Richter (≈ 0,1 % con M ≥ 4) y un 30 % sin país.
- **Índices**: `bench` se crea con la plantilla de tablas, que **no** incluye los índices secundarios de `db/sql/060_indexes.sql`. Se mide primero así (peor caso) y
  después creando los tres índices de `event_current` (`event_time`, `country_id + event_time`, `magnitude + event_time`), que es lo que tienen `core` y `replay`.
- Salida literal: [api-latency-1m-no-indexes.out](api-latency-1m-no-indexes.out) y [api-latency-1m-with-indexes.out](api-latency-1m-with-indexes.out).

## Resultado (ms; 30 medidas)

| Consulta | Filas tras el filtro | Sin índices: mediana / p95 / máx. | Con índices: mediana / p95 / máx. |
|---|---:|---|---|
| `/api/eventos?limit=10` | 1.000.000 | 468,4 / 523,2 / 541,0 | 166,8 / 182,9 / 192,0 |
| `/api/eventos?limit=1000` | 1.000.000 | 494,9 / 703,9 / 913,5 | 182,0 / 194,4 / 207,0 |
| `/api/eventos?limit=1000` de 2025 | 1.000.000 | 539,9 / 605,8 / 626,7 | 190,6 / 208,6 / 213,5 |
| `/api/estadisticas` de 2025, sin filtro | 1.000.000 | 1.056,4 / 1.142,4 / 1.210,3 | 1.276,4 / 1.333,7 / 1.412,6 |
| `/api/estadisticas` de 2025, `min_mag=4` | 1.060 / 1.016 | 607,2 / 665,2 / 707,3 | 449,1 / 487,0 / 517,8 |

(Las filas con M ≥ 4 son 1.060 y 1.016: son dos cargas sintéticas distintas.)

**Esperado**: mediana ≤ 2.000 ms en todas, sin fallos (SC-008 de la 006). **Observado**: máxima mediana 1.276,4 ms, 0 fallos. **Comparación con la 006**
(34.045 eventos, equipo y método equivalentes pero la 006 medía por HTTP desde otro contenedor): 3,0 / 20,4 / 80,8 ms. Con ×29 más filas, con índices: página pequeña 3,0 → 166,8 ms (×56), página completa 20,4 → 182,0 ms (×9) y estadísticas de un año con `min_mag=4` 80,8 → 449,1 ms (×5,6); sin filtro, 1.276,4 ms. La página pequeña no es comparable: la 006 usaba la ventana de 24 h por defecto (33 eventos) y aquí el modo `replay` cuenta 1.000.000.

## Lectura

- Las páginas de eventos pasan de ≈ 470–540 ms a ≈ 170–190 ms con índices: en `replay` sin ventana por defecto la API cuenta todos los eventos del filtro
  (`total` exacto), y con el índice de `event_time` ese recuento se resuelve sin leer la tabla.
- `/api/estadisticas` sin filtro sobre 1.000.000 de filas tarda ≈ 1,1–1,3 s con y sin índices: agrega todas las filas del año y los índices no ayudan (la
  variación entre las dos ejecuciones es ruido de la máquina, no un efecto de los índices; no se ha investigado más). Es la consulta más cara y la que primero
  se acercaría al límite de 2.000 ms con más datos.
- La estadística con `min_mag=4` tarda ≈ 450–600 ms aunque solo devuelve ≈ 1.000 filas: tiene otros componentes de coste fijo (8.760 ventanas horarias, el
  recuento por país y la comparación histórica) que no dependen del filtro; no se ha desglosado.

## Aislamiento (V7)

| Comprobación | Esperado | Observado (15:03 UTC) |
|---|---|---|
| Esquema `bench` tras la medición | no existe | 0 esquemas `bench` |
| `core.event_current` anterior a 2026 | 18.302 (igual que antes) | 18.302 |
| `core` con identificador `synthetic-%` | 1.013 (igual que antes) | 1.013 |
| `replay.event_current` | 2.807 (igual que antes) | 2.807 |

**Límites**: una sola máquina, con carga de fondo; medición en proceso (sin red ni túnel, que añadirían latencia); datos sintéticos uniformes que no reproducen la
agrupación de los reales; los tiempos no son una garantía para otro equipo.
