# Evidencia de la spec 006: API de consulta

Índice de los escenarios V1–V16 de [quickstart.md](../../../specs/006-query-api/quickstart.md).
El entorno de cada ejecución se describe en [00-environment.md](00-environment.md).

Cada fichero de evidencia guarda el resultado esperado, el observado y la salida, según la skill
`verify-stack`. Un escenario solo está superado cuando su fichero existe con el resultado observado
y el estado de esta tabla se actualiza.

| Id | Qué comprueba | Fichero de evidencia previsto | Estado |
|---|---|---|---|
| V1 | Forma del contrato: `FeatureCollection`, `metadata` completo, coordenadas `[lon, lat, prof]`, tiempos enteros, ningún NaN | `v1-contract.md` | superada |
| V2 | Filtros `start`, `end` (exclusivo), `min_mag`, `country_id` y combinados | `v2-filters.md` | superada |
| V3 | Evento nuevo aparece una vez; repetirlo no sube `total` | `v3-new-and-repeat.md` | superada |
| V4 | Revisión posterior actualiza datos y `updated`; versión antigua no cambia nada | `v4-revision-and-stale.md` | superada |
| V5 | Magnitud nula: `mag: null` sin filtro; fuera con `min_mag` y `null_magnitude.excluded: true` | `v5-null-magnitude.md` | superada |
| V6 | Coordenadas inválidas: ningún `Feature` sin punto; `quarantined.invalid_geometry` +1 | `v6-geometry.md` | superada |
| V7 | Evento sin país: `country_id: null`, bajo «Sin país asignado», no filtrado por `country_id` | `v7-no-country.md` | superada |
| V8 | Truncado y paginación con `next_offset`: `truncated: true`, cada evento una sola vez | `v8-truncation.md` | superada |
| V9 | Reproducción: `mode: replay`, `label: REPRODUCCIÓN`, `replayed_at` por `Feature`, sin ventana de 24 h | `v9-replay.md` | superada |
| V10 | Aislamiento: conteos `live` idénticos antes y después de reproducir | `v10-isolation.md` | superada |
| V11 | Estadísticas: total igual al del mapa, horas vacías con 0, `ND`, aviso y nulos aparte | `v11-statistics.md` | superada |
| V12 | Base caída: salud `degraded`, eventos y estadísticas 503 en JSON, vuelta a `ok` sin reiniciar la API | `v12-database-down.md` | superada |
| V13 | Validación 422 y CORS solo para orígenes permitidos, sin `Allow-Credentials` | `v13-validation-cors.md` | superada |
| V14 | Superficie: solo las rutas del contrato, 405 en escritura, respuesta siempre `FeatureCollection` | `v14-surface.md` | superada |
| V15 | Planes e índices: `EXPLAIN (ANALYZE, BUFFERS)` usa los índices de la spec 002 | `v15-plans.md` | superada |
| V16 | Latencia por tamaños, mediana, p95 y máximo (SC-008), con equipo y procedimiento | `v16-latency.md` | superada |
