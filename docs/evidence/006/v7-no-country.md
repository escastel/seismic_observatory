# V7 · Evento marítimo sin país dentro del análisis

**Fecha**: 2026-11-16 · **Rama**: `006-query-api` · **Resultado**: SUPERADA

**Procedimiento**: prueba de comportamiento que llama a la aplicación real de la API (la misma que despliega el contenedor) contra la base `observatory_test` con el modelo de las specs 002 a 004 aplicado con `db/sql/apply.sh`, escribiendo con `apply_event_version` (la función del consumidor). Se usa esa base y no la local del sistema levantado porque estos casos necesitan mensajes concretos y **nunca se insertan eventos sintéticos en el `core` real**. Salida completa: [v3-v7-behavior-tests.out](v3-v7-behavior-tests.out) (75 de 75 pruebas de `tests/query_api` en verde).

| Comprobación | Esperado | Prueba (observado: PASSED) |
|---|---|---|
| Mapa | aparece con `country_id: null` sin filtro de país y no con `country_id=...` | `test_events_contract.py::test_maritime_event_appears_without_country_filter_and_not_with_it` |
| Estadísticas | «Sin país asignado» es una categoría válida y la suma por países es igual al total | `test_statistics.py (pruebas de países)` |

Sistema real (2025, `/api/estadisticas`): 14.350 de 18.302 eventos figuran bajo «Sin país asignado» (país nulo), y la suma de países coincide con el total (comprobado en V11).
