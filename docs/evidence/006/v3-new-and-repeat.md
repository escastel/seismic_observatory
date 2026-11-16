# V3 · Evento nuevo visible y mensaje repetido sin aumentar el recuento

**Fecha**: 2026-11-16 · **Rama**: `006-query-api` · **Resultado**: SUPERADA

**Procedimiento**: prueba de comportamiento que llama a la aplicación real de la API (la misma que despliega el contenedor) contra la base `observatory_test` con el modelo de las specs 002 a 004 aplicado con `db/sql/apply.sh`, escribiendo con `apply_event_version` (la función del consumidor). Se usa esa base y no la local del sistema levantado porque estos casos necesitan mensajes concretos y **nunca se insertan eventos sintéticos en el `core` real**. Salida completa: [v3-v7-behavior-tests.out](v3-v7-behavior-tests.out) (75 de 75 pruebas de `tests/query_api` en verde).

| Comprobación | Esperado | Prueba (observado: PASSED) |
|---|---|---|
| Evento nuevo | tras escribir un mensaje válido aparece en `/api/eventos` una vez | `test_events_ingestion_flow.py::test_new_event_is_visible_after_it_is_written` |
| Mismo mensaje repetido | `total` no cambia; sigue una sola versión vigente | `test_events_ingestion_flow.py::test_the_same_message_twice_does_not_change_the_total` |
