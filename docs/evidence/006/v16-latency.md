# V16 · Latencia de la API en tres tamaños de resultado

**Fecha**: 2026-11-16 · **Rama**: `006-query-api` · **Resultado**: SUPERADA (SC-008)

## Equipo y procedimiento (§10)

- **Equipo**: Intel Core i5-11400H (2,70 GHz, 12 hilos lógicos), 15,7 GB de RAM en el equipo y 7,6 GiB
  visibles en la máquina virtual WSL2 de Docker Desktop; Windows 11 Pro; Docker 29.1.3.
- **Orden**: `docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python3 tests/benchmark/api_latency.py --base-url http://api:8000`
  (el cliente corre en la misma red de Compose que la API, sin túnel).
- **Método**: 5 peticiones de calentamiento y 30 medidas secuenciales por tamaño, solo `GET`;
  se informa mediana, p95 y máximo en milisegundos. El resto de servicios (productor, consumidor,
  Kafka) seguían activos durante la medición.
- **Datos**: modo real (esquema `core`), 34.045 eventos actuales; 18.302 de 2025 con magnitud ≥ 4
  (los demás eventos son del feed en vivo y de pruebas).

## Resultado

| Tamaño de resultado | Petición | Eventos tras el filtro | Mediana | p95 | Máximo |
|---|---|---|---|---|---|
| Pequeño | `/api/eventos?limit=10` (ventana por defecto) | 33 | 3,0 ms | 3,6 ms | 3,8 ms |
| Página completa | `/api/eventos?limit=1000` sobre 2025 | 18.302 | 20,4 ms | 22,5 ms | 178,6 ms |
| Estadísticas de un año | `/api/estadisticas` de 2025 con `min_mag=4` | 18.302 | 80,8 ms | 94,5 ms | 108,6 ms |

**Esperado**: mediana ≤ 2.000 ms en los tres tamaños, sin fallos (SC-008). **Observado**: todas las
medianas por debajo de 100 ms y 0 fallos.

La salida literal de la orden termina con `SC-008 (median <= 2000 ms, no failures): PASS`. El máximo
de 178,6 ms de la página completa es una muestra aislada (la primera tras cambiar de consulta).

## Por qué ventanas fijas de una hora UTC

- Son **reproducibles**: la misma consulta devuelve las mismas ventanas en cualquier instante; una
  ventana deslizante («la última hora») cambiaría en cada petición y no sería comparable entre mapa,
  tabla y estadísticas (constitución VII).
- Se calculan con `date_bin` alineado a la hora UTC, **independiente de la zona horaria de la sesión**
  de PostgreSQL, y el extremo final queda excluido: un evento a las 11:00:00,000 pertenece a la
  ventana de las 11:00 y no a la de las 10:00 (comprobado en `tests/query_api/test_statistics.py`).
- Se resuelven en **una pasada** sobre el estado actual (un `GROUP BY` sobre el rango de
  `event_time`) y se rellenan las horas vacías con `generate_series`, así que el coste crece con el
  número de eventos y no con el de ventanas. Un año completo son 8.760 ventanas y 81 ms; por encima
  de 10.000 ventanas la API pide acotar el periodo en lugar de truncar.
- La alternativa de contadores incrementales por ventana se descartó por el principio VII y porque
  una revisión o una versión antigua tardía los dejaría inconsistentes con el estado actual.

## Límites

- Una sola máquina, con carga de fondo; los tiempos no son una garantía para otro equipo.
- Con el esquema `bench` de 1.000.000 de filas de la spec 002 no se ha medido (no está cargado aquí);
  los planes de [v15-plans.md](v15-plans.md) indican que las consultas de página usan el índice por
  `event_time` y se detienen en `LIMIT`, pero el comportamiento a ese tamaño es una extrapolación.
