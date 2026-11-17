# Matriz de las 11 pruebas de aceptación de §11 (T022)

**Construida**: 2026-11-17, leyendo los `README.md` de [002](../002/README.md), [003](../003/README.md), [004](../004/README.md),
[005](../005/README.md), [006](../006/README.md) y [007](../007/README.md). «Superada» solo cuando la evidencia enlazada
tiene resultado esperado y observado ejecutados; no se ha repetido ninguna prueba para esta matriz. Todas se ejecutaron en el
equipo Windows 11 descrito en cada evidencia.

| # | Prueba de §11 | Resultado esperado | Spec | Evidencia | Estado | Hueco |
|---|---|---|---|---|---|---|
| 1 | Recibir un evento nuevo | Una fila actual, visible en API, mapa y análisis | 004, 006, 007 | [006 V3](../006/v3-new-and-repeat.md); [007 V2](../007/README.md) (aparece sin recargar, 0 duplicados); [004 V2](../004/acceptance.md) | superada | — |
| 2 | Reenviar la misma versión | No aumenta el número de terremotos | 002, 004, 005, 006 | [006 V3](../006/v3-new-and-repeat.md); [004 acceptance](../004/acceptance.md) («Publicados 0, omitidos 31»); [005 V5](../005/v5-repeat.md); pruebas de base en [002 db-tests](../002/db-tests.txt) | superada | — |
| 3 | Recibir una versión posterior | Cambian los datos actuales y las agregaciones afectadas | 002, 006 | [006 V4](../006/v4-revision-and-stale.md); [006 V11](../006/v11-statistics.md) (estadísticas derivadas del estado actual) | superada | — |
| 4 | Recibir después una versión antigua | No sustituye a la más reciente | 002, 006 | [006 V4](../006/v4-revision-and-stale.md); regla `stale` de `apply_event_version` en [002 db-tests](../002/db-tests.txt) | superada | — |
| 5 | Magnitud nula | Se conserva con tratamiento documentado y se visualiza como ND | 004, 006, 007 | [004 acceptance](../004/acceptance.md); [006 V5](../006/v5-null-magnitude.md); [007 V3](../007/README.md) (con simulador de contrato: el sistema real no puede producirlo sin datos sintéticos en `core`) | superada | La visualización ND se comprobó con simulador, no con un evento real nulo |
| 6 | Coordenadas inválidas | Cuarentena y motivo; no aparecen puntos inventados | 004, 006, 007 | [004 acceptance](../004/acceptance.md); [006 V6](../006/v6-geometry.md); [007 V5](../007/README.md) (simulador) | superada | Igual que la 5 |
| 7 | Evento marítimo | Sin país asignado; permanece en el análisis | 004, 006, 007, 008 | [004 acceptance](../004/acceptance.md); [006 V7](../006/v7-no-country.md); [007 V4](../007/README.md) (real); [008 C1](analysis-queries.md): 14.350 de 18.302 eventos reales de 2025 sin país | superada | — |
| 8 | Reiniciar consumidor | Reanuda sin duplicar los efectos ya persistidos | 004, 005 | [004 V3](../004/restart.md) (muerto tras 357 de 1.000; al reiniciar 1.000 eventos, 1.000 versiones, offsets sin huecos); [005 V7](../005/v7-consumer-restart.md) | superada | Prueba en Linux pendiente (ver [user-gaps.md](user-gaps.md), G3) |
| 9 | Cerrar el túnel | El panel muestra el fallo y conserva/identifica la última lectura | 007 | [007 T2 y V11](../007/README.md) (túnel real, aviso a los 55 s con 165 eventos conservados); capturas `T2-tunnel-closed.png` y `N3-netlify-tunnel-closed.png` | superada | — (probada también en un móvil con datos móviles, [007 M2](../007/README.md)) |
| 10 | Volver a abrir el túnel | Se recuperan las consultas automáticamente | 007 | [007 T2](../007/README.md) (recuperación a los 61 s sin recargar); `T3-tunnel-reopened.png` y `N4-netlify-tunnel-reopened.png` | superada | — (probada también en un móvil, [007 M3](../007/README.md)) |
| 11 | Reproducción histórica | Procesa por Kafka sin mezclarla con datos live | 005, 006, 007 | [005 V1–V9](../005/README.md); [006 V9 y V10](../006/v10-isolation.md); [007 V9 y V10](../007/README.md) | superada | Prueba en Linux pendiente (G3) |

**Resumen**: 11 de 11 con evidencia ejecutada en Windows; 0 pruebas sin evidencia. Los huecos no cambian el estado de la prueba en
el equipo en que se ejecutó, pero **no se puede afirmar** que pasen en Linux (G3) hasta que la usuaria
ejecute los procedimientos de [user-gaps.md](user-gaps.md). Las pruebas 9 y 10 se repitieron el 2026-11-17 desde un móvil con datos móviles (G4, [007 M1 a M3](../007/README.md)). Las pruebas 5 y 6 se demostraron en la API con casos reales de la
base (sintéticos aislados) y en el panel con simulador; no hay un evento real con magnitud nula en los datos de USGS cargados.
