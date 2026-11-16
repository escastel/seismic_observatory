# V5 · Magnitud nula conservada y contada

**Fecha**: 2026-11-16 · **Rama**: `006-query-api` · **Resultado**: SUPERADA

**Procedimiento**: prueba de comportamiento que llama a la aplicación real de la API (la misma que despliega el contenedor) contra la base `observatory_test` con el modelo de las specs 002 a 004 aplicado con `db/sql/apply.sh`, escribiendo con `apply_event_version` (la función del consumidor). Se usa esa base y no la local del sistema levantado porque estos casos necesitan mensajes concretos y **nunca se insertan eventos sintéticos en el `core` real**. Salida completa: [v3-v7-behavior-tests.out](v3-v7-behavior-tests.out) (75 de 75 pruebas de `tests/query_api` en verde).

| Comprobación | Esperado | Prueba (observado: PASSED) |
|---|---|---|
| Con y sin `min_mag` | sin filtro: `mag: null` y `excluded: false`; con `min_mag`: fuera de `features` y `excluded: true` con su recuento | `test_events_contract.py::test_null_magnitude_with_and_without_min_mag` |
| Estadísticas | las magnitudes y profundidades nulas van a `unvalued` y los tramos más `unvalued` suman el total | `test_statistics.py::test_null_magnitudes_and_depths_are_unvalued_and_everything_adds_up` |

En el sistema real local no hay ningún evento con magnitud nula (`unvalued = 0` en 2025 y en la ventana por defecto), por eso este caso solo se puede demostrar con datos de prueba.
