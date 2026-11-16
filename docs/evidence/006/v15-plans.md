# V15 · Planes de ejecución e índices

**Fecha**: 2026-11-16 · **Rama**: `006-query-api` · **Equipo**: ver [00-environment.md](00-environment.md) ·
**Resultado**: SUPERADA

**Procedimiento**: `EXPLAIN (ANALYZE, BUFFERS)` de las consultas que emite la API, con los mismos
predicados y órdenes ([sql/v15-plans.sql](sql/v15-plans.sql)), sobre la base local (esquema `core`:
34.045 eventos; `replay`: 5.301 antes de V10; `extraction`: 444+ filas). Salida completa en
[v15-plans.out](v15-plans.out).

**Esperado**: las consultas usan los índices de la spec 002 y no hay escaneo secuencial salvo donde el
predicado selecciona una parte grande de la tabla.

| Consulta | Índice usado | Tiempo de ejecución | Observación |
|---|---|---|---|
| Q1 ventana por defecto (24 h), página de 1000 | `event_current_event_time_idx` (barrido inverso) + ordenación incremental por `event_id` | 0,46 ms | 196 filas leídas |
| Q2 año 2025 con `min_mag`, página de 1000 | `event_current_event_time_idx` (barrido inverso) + ordenación incremental | 2,08 ms | lee 1.001 filas y se detiene: `LIMIT` empujado al índice |
| Q3 país + periodo (total) | `event_current_country_event_time_idx` (bitmap) | 4,93 ms | 129 filas |
| Q4 solo magnitud, sin periodo (total) | `event_current_magnitude_event_time_idx` (bitmap) | 7,52 ms | 433 entradas de índice, 272 filas |
| Q5 estadísticas por hora, año 2025 con `min_mag` | escaneo secuencial | 27,2 ms | el predicado selecciona 18.302 de ~34.000 filas (más de la mitad): el planificador elige correctamente el escaneo secuencial |
| Q6 última ingesta | `extraction_last_ok_feed_idx` (solo índice, barrido inverso) | 0,03 ms | 1 fila leída |
| Q7 cuarentena | escaneo secuencial | 0,05 ms | tabla de 2 filas |
| Q8 reproducción, página sin periodo | `event_current_event_time_idx` + ordenación incremental | 1,83 ms | 1.001 filas leídas |

**Observado / conclusión**: las consultas de la página, los recuentos por país y por magnitud y la
última ingesta usan los índices existentes. Los dos escaneos secuenciales (Q5 y Q7) son decisiones
correctas del planificador: uno recorre más de la mitad de la tabla y el otro una tabla de 2 filas.
La ordenación por `(event_time DESC, event_id)` no necesita índice nuevo: el índice por
`event_time` entrega las filas ordenadas y PostgreSQL solo desempata dentro de cada grupo de
tiempos iguales (*Incremental Sort*). **No se añade ningún índice ni se cambia el modelo.**

**Límite de esta medición**: se hizo con 34.045 eventos reales. No se repitió con el esquema
`bench` de 1.000.000 de filas de la spec 002 (no está cargado en este equipo); la extrapolación a
ese tamaño queda como supuesto y no como medida.
