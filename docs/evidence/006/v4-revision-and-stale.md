# V4 · Versión posterior que cambia datos y agregaciones; versión antigua tardía

**Fecha**: 2026-11-16 · **Rama**: `006-query-api` · **Resultado**: SUPERADA

**Procedimiento**: prueba de comportamiento que llama a la aplicación real de la API (la misma que despliega el contenedor) contra la base `observatory_test` con el modelo de las specs 002 a 004 aplicado con `db/sql/apply.sh`, escribiendo con `apply_event_version` (la función del consumidor). Se usa esa base y no la local del sistema levantado porque estos casos necesitan mensajes concretos y **nunca se insertan eventos sintéticos en el `core` real**. Salida completa: [v3-v7-behavior-tests.out](v3-v7-behavior-tests.out) (75 de 75 pruebas de `tests/query_api` en verde).

| Comprobación | Esperado | Prueba (observado: PASSED) |
|---|---|---|
| Revisión posterior | cambian `mag`, `updated` y el país; la agregación por país y por magnitud mueve el evento | `test_events_ingestion_flow.py::test_a_revision_changes_magnitude_updated_and_country; test_statistics.py::test_a_revision_moves_the_event_between_bins_and_countries` |
| Versión antigua tardía | no sustituye al estado actual ni altera el mapa ni las agregaciones | `test_events_ingestion_flow.py::test_a_late_older_version_changes_nothing` |
