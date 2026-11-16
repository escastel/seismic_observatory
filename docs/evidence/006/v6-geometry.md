# V6 · Coordenadas inválidas sin punto

**Fecha**: 2026-11-16 · **Rama**: `006-query-api` · **Resultado**: SUPERADA

**Procedimiento**: prueba de comportamiento que llama a la aplicación real de la API (la misma que despliega el contenedor) contra la base `observatory_test` con el modelo de las specs 002 a 004 aplicado con `db/sql/apply.sh`, escribiendo con `apply_event_version` (la función del consumidor). Se usa esa base y no la local del sistema levantado porque estos casos necesitan mensajes concretos y **nunca se insertan eventos sintéticos en el `core` real**. Salida completa: [v3-v7-behavior-tests.out](v3-v7-behavior-tests.out) (75 de 75 pruebas de `tests/query_api` en verde).

| Comprobación | Esperado | Prueba (observado: PASSED) |
|---|---|---|
| Mensaje con coordenadas inválidas | evaluado por las reglas del consumidor (spec 004) va a cuarentena; ningún `Feature` sin punto; `quarantined.invalid_geometry` sube exactamente en 1 | `test_events_ingestion_flow.py::test_a_message_with_invalid_coordinates_is_quarantined_not_shown` |
| Cuarentena sintética o de otro motivo | la sintética no se cuenta; otros motivos suben solo `total` | `test_events_ingestion_flow.py::test_synthetic_quarantine_is_not_counted; test_events_ingestion_flow.py::test_non_geometry_quarantine_counts_in_total_only` |

El modelo impide además que un evento sin punto válido esté en el estado actual (`longitude`/`latitud` `NOT NULL` y con rango): la API no puede devolverlo. Sistema real: `quarantined = {total: 2, invalid_geometry: 0}`.
