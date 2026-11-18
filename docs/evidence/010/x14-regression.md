# X14. No regresión (T032)

Chrome contra el panel de la rama y la **API real local**; donde el sistema real no produce el caso se alteraron las respuestas en el navegador (interceptación de peticiones; ni el repositorio ni la base cambian). En bruto: [x14-regression.json](x14-regression.json) y [x14-pagination.json](x14-pagination.json).

## Pruebas automáticas y ficheros

- `npm test` (Vitest): **18 ficheros, 199 pruebas en verde** (las 142 anteriores más 57 nuevas).
- `pytest tests/query_api` (una sola ejecución, contenedor `tests`): **79 pruebas en verde**, con las 4 nuevas de estadísticas sin eventos.
- `git diff origin/main` de `adapt.ts`, `api-types.ts`, `filters.ts`, `status.ts`, `config.ts` y `summary.ts`: **vacío**. Los únicos cambios en lo existente son `api/app/stats.py` y `observatory.service.ts` (7 líneas, justificados en [x1-api-fix.md](x1-api-fix.md)).

## Escenarios de la 007 con el panel nuevo

| Id | Qué comprueba | Observado | Estado |
|---|---|---|---|
| V1 | Carga con la API real | 193 eventos en mapa, tabla y barra, igual que `/api/estadisticas` (193); 0 errores de consola | SUPERADA |
| V3 | Nulos como ND | magnitud y profundidad nulas como «ND» en la tabla | SUPERADA |
| V4 | Evento sin país | «Sin país asignado» en la tabla | SUPERADA |
| V5 | Texto como texto y coordenadas | `<img … onerror=…>` aparece como texto literal; `window.__xss` sin definir; «1 omitidos por coordenadas no válidas» | SUPERADA |
| V6 | Truncado y paginación | reproducción: «Mostrando 1000 de 2807», aviso de truncado; tras «Cargar más», 2807 de 2807, 2807 ids únicos, botón deshabilitado | SUPERADA |
| V7 | Filtros coherentes | barra, mapa, tabla y gráficos coinciden con la API en tres juegos de filtros (194, 10 con magnitud ≥ 5, 0 con país JPN) | SUPERADA |
| V8 | Filtros inválidos | inicio posterior al fin: «El inicio debe ser anterior al fin.» y no se pide nada; más de 10 000 horas: aviso de estadísticas (ver [X6](x6-alerts.md)). La magnitud solo se valida como número (99 es válido) | SUPERADA |
| V9/V10 | Reproducción etiquetada y aislada | «REPRODUCCIÓN» en barra, mapa y avisos, total 2807 = API; al volver a en vivo, 194 como antes | SUPERADA |
| V11 | Backend inaccesible y recuperación | error con la última lectura conservada (194 eventos y 194 filas); al volver, «Conexión recuperada» sin recargar; una respuesta HTML se trata como inaccesible | SUPERADA |
| V12 | Estados distintos | 503, 422 de estadísticas y datos desactualizados verificados en [X6](x6-alerts.md) | SUPERADA |
| V13 | Sin solapes y tiempo de espera | **no repetida de forma equivalente**: con cuatro «Aplicar» seguidos y respuestas de 3 s hubo hasta 4 peticiones de eventos a la vez; la 009 lo midió con el ciclo del temporizador (respuesta de 9 s, tiempo de espera 4 s). `observatory.service.ts` solo cambia en la tolerancia de estadísticas | NO REPETIDA |
| Ficha | Teclado | se abre desde «Ver ficha», foco inicial en «Cerrar», se cierra con Escape | SUPERADA |
| V14 | axe | ver [X13](x13-a11y.md): 0 violaciones en 14 estados | SUPERADA |
| V2 | Evento nuevo sin recargar | no repetida (cada refresco recarga sin navegar; no se esperó a un evento nuevo de USGS) | NO REPETIDA |

Pendiente: cierre y reapertura del túnel real (T033) y repetición en Netlify tras el merge (X16).
