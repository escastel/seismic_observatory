# Evidencia spec 007: panel Angular

**Fecha**: 2026-11-16 · **Rama**: `007-angular-dashboard` · **Equipo**: Windows 11, Chrome headless (Puppeteer) contra el panel servido con `ng serve` en `http://localhost:4200`, Node 24.

Hay **dos orígenes de datos** y cada fila dice cuál se usó:

- **API real**: la API de la 006 del stack local (`http://127.0.0.1:8000`), con los datos reales de 2025 (18.302 eventos), la ventana de 24 h ingerida en vivo y la reproducción de la spec 005 (2.807 eventos).
- **Simulador de contrato**: un servidor de unos 100 líneas (fuera del repositorio) que habla el contrato de la 006. Se usa solo para lo que el sistema real no puede producir sin insertar datos sintéticos en `core` (prohibido en la spec 006): magnitud o profundidad nula, texto con marcas, coordenadas inválidas, más de 1.000 eventos en 24 h, 503, página no JSON y datos desactualizados. Esos mismos casos de la **API** ya están demostrados con pruebas en `docs/evidence/006/`; aquí se comprueba **el panel**.

Para ejecutar los escenarios se cambió temporalmente `apiUrl` de `frontend/public/config.json` a la API local o al simulador y se restauró al terminar (`git diff` solo muestra los campos nuevos de la configuración). Resultados en bruto: [real-scenarios.json](real-scenarios.json), [mock-scenarios.json](mock-scenarios.json), [v2-new-event.json](v2-new-event.json), [a11y.json](a11y.json). Pruebas de lógica pura: `npm test` en `frontend/` (8 ficheros, 106 pruebas, todas en verde).

## Resultados

| Id | Qué comprueba | Origen | Esperado | Observado | Estado |
|---|---|---|---|---|---|
| V1 | Carga con la API de la 006 | real | sin NG0900; mapa, tabla y gráficos con datos de 24 h | sin errores de aplicación en consola; 195 eventos en mapa, 195 en tabla, total 195 en estadísticas ([captura](V1-panel.png)). Los únicos errores de red de consola son las teselas de OpenStreetMap rechazadas por el navegador sin interfaz (400) y `favicon.ico` (404) | SUPERADA |
| V1b | Hallazgo real durante V1 | real | el panel acepta la respuesta real | el primer intento falló con «depth.from»: la API entrega tramos de profundidad abiertos (`from: null` en «<0», `to: null` en «>=300») y el adaptador los rechazaba. Corregido y con prueba de regresión (`adapt.test.ts`) | corregido |
| V2 | Evento nuevo sin recargar | real | aparece en mapa y tabla en un refresco, sin duplicados ni recarga | tras 3 min de espera apareció `aka2026wszejn` (presente en la API), 0 duplicados, 1 navegación (no hubo recarga) ([v2-new-event.json](v2-new-event.json)) | SUPERADA |
| V3 | Nulos como ND | simulador | magnitud y profundidad nulas como ND; el 0 sigue siendo 0 | `null-mag`: magnitud «ND»; `null-depth`: profundidad «ND» ([captura](V3-V5-nulls.png)). El 0 y los formatos están cubiertos por `format.test.ts` | SUPERADA |
| V4 | Evento marítimo | real | «Sin país asignado» en ficha/tabla y en el gráfico por país, no filtrable | 27 filas de la tabla con «Sin país asignado» = 27 en el gráfico por país; ejemplo `hv75071182` (Hawaii, mar); el selector de país no ofrece esa opción y lo explica | SUPERADA |
| V5 | Texto como texto y coordenadas | simulador | `<img onerror>` se muestra literal; coordenadas inválidas omitidas y contadas | la fila muestra el texto literal; `window.__xss` no se ejecutó; «5 eventos dibujados · 1 omitidos por coordenadas no válidas» | SUPERADA |
| V6 | Truncado y paginación | real (2025) y simulador (2.500) | aviso visible; «Mostrando N de TOTAL»; sin repetidos; estadísticas = total | 2025 completo: «1000 de 18302», aviso de respuesta truncada, tras dos «Cargar más» 3000 filas, 3000 únicas; estadísticas 18.302 = total de la API ([captura](V6-real-2025.png)). Simulador: 1000 → 2000 → 2500, botón deshabilitado al final, 2500 únicas, aviso de estadísticas `scope: complete` ([captura](V6-truncation.png)) | SUPERADA |
| V7 | Filtros coherentes | real | totales de tabla, mapa y estadísticas iguales entre sí e iguales a la API con los mismos filtros | 6 combinaciones (sin filtro, `min_mag` 4, país USA, USA + `min_mag` 2, fechas UTC, fechas + `min_mag` + país): tabla = mapa = estadísticas en las 6. Las 5 con periodo cerrado o filtros estables coinciden además con la API (15, 158, 46, 114, 0). En «sin filtro» la ventana de 24 h se mueve: la API dio 194 y el panel 195 porque entró un evento entre las dos lecturas; las tres vistas del panel coinciden entre sí. Capturas `V7-filter-1..6.png` | SUPERADA |
| V8 | Filtros inválidos | real | inicio ≥ fin: error junto al campo y vista conservada; > 10.000 h: se explica | «El inicio debe ser anterior al fin.» y la vista anterior se conserva ([captura](V8-start-after-end.png)). 2025-01-01 hasta ahora (16.440 ventanas): eventos y tabla correctos y aviso «El periodo supera las 10.000 horas: acota las fechas» en el análisis ([captura](V8-over-10000h.png)) | SUPERADA |
| V9 | Reproducción etiquetada | real | «REPRODUCCIÓN» en estado, mapa, tabla y gráficos; última reproducción; sin ventana de 24 h | etiqueta de `metadata.label` presente en las cuatro zonas; «Última reproducción 2026-11-16 18:55:09 UTC»; periodo elegido sin ventana por defecto; 2.807 eventos = total de la API; columnas `replayed_at` y «Sintético» ([captura](V9-replay.png)) | SUPERADA |
| V10 | Aislamiento | real | tras reproducir y volver, los totales reales no cambian | mismo periodo 2025: real 18.302 → reproducción 2.807 → real 18.302 | SUPERADA |
| V11 | Cerrar y reabrir el túnel | simulador (y bloqueo de red del navegador) | aviso de backend inaccesible con la última lectura rotulada; recuperación en el siguiente refresco | con la red bloqueada: «No se puede contactar con el backend. Se muestra la última lectura correcta», con la hora de la última lectura y los 6 eventos conservados ([captura](V11-unreachable.png)); al restablecer, vuelve a «Datos al día» sin recargar. Respuesta HTML (página intermedia de ngrok) tratada como inaccesible | SUPERADA (ver nota) |
| V12 | Estados distintos | simulador | mensajes diferentes para 503, `degraded`, 422 y desactualizado | 503: «La base de datos no está disponible (503). Esto no significa que no haya eventos» + degradado ([captura](V12-503.png)); 422 de estadísticas: «el periodo supera las 10000 ventanas horarias»; desactualizado: «hace 40 min»; sin eventos (real, filtro con 0 resultados): «Sin eventos para este periodo y estos filtros» | SUPERADA |
| V13 | Sin solapes y 15 s | simulador | una sola petición en curso; a los 15 s inaccesible | respuesta retrasada 20 s: a los 17 s el panel marca inaccesible con la lectura conservada, máximo 1 petición de eventos en vuelo | SUPERADA |
| V14 | Teclado y lector | real | todo operable con teclado; sin violaciones de accesibilidad automáticas | `lang="es"`; orden de tabulación: enlace «Saltar a la tabla», modo, fechas, magnitud, país, aplicar, restablecer, mapa; foco visible en todos; cambio de modo con la barra espaciadora; regiones `aria-live` en estado y tabla; axe-core (WCAG 2.0/2.1 A y AA): 0 violaciones tras corregir 3 de estructura (lista de definición, lista con roles y región desplazable sin foco) ([a11y.json](a11y.json)) | SUPERADA (ver nota) |
| V15 | Build y secretos | local | build limpio sin secretos | `npm run build` sin errores (aviso conocido: Leaflet no es ESM); el paquete `dist/observatorio/browser` no contiene `authtoken`, `password` ni `secret`; `config.json` solo con URL, intervalos y banderas | SUPERADA |

## Prueba con el túnel ngrok real (2026-11-17)

Hecha con el servicio `tunnel` de Compose y el dominio reservado de la cuenta (`modular-guidance-daybreak.ngrok-free.dev`, comprobado con la API de ngrok: un dominio y sin agentes conectados antes de levantarlo). El túnel se paró al terminar; antes de la prueba no estaba levantado.

| Id | Qué comprueba | Esperado | Observado | Estado |
|---|---|---|---|---|
| T1 | El túnel sirve la API | `/api/salud` y el preflight desde `http://localhost:4200` a través del dominio público | `{"status":"ok",...}` y preflight 200 con `Access-Control-Allow-Origin: http://localhost:4200` y la cabecera `ngrok-skip-browser-warning` permitida | SUPERADA |
| T2 | **Cerrar y reabrir el túnel** (V11 real, refresco de 60 s sin forzar) | aviso de inaccesible con la última lectura rotulada; recuperación sin recargar | con el panel abierto se paró el túnel: el aviso apareció a los 55 s (siguiente refresco) con los 165 eventos conservados y «los datos mostrados son la última lectura correcta, del 14:01:26 UTC»; al reabrirlo, el panel volvió a «Datos al día» a los 61 s sin recargar (1 navegación en toda la prueba) ([túnel abierto](T1-tunnel-open.png), [cerrado](T2-tunnel-closed.png), [reabierto](T3-tunnel-reopened.png), [datos](tunnel-real.json)) | SUPERADA |
| T3 | Build de producción contra el túnel | el paquete `dist/observatorio/browser`, servido como sitio estático con la misma regla SPA que `_redirects`, lee del túnel | 165 eventos dibujados y 165 en tabla, sin NG0900, peticiones `GET` 200 a `https://modular-guidance-daybreak.ngrok-free.dev/api/...` ([captura](T4-prod-build-tunnel.png), [datos](prod-build-real-tunnel.json)) | SUPERADA |

## Prueba desde Netlify (2026-11-17)

Sitio publicado por la persona autora: `https://seismicobservatoryecr.netlify.app`, con el panel de la spec 007 (su `config.json` apunta al dominio del túnel) y el origen exacto del sitio añadido a `CORS_ORIGINS` (preflight comprobado: el sitio y `http://localhost:4200` reciben 200 con su origen; un origen ajeno, 400). Navegador automatizado sobre la URL pública, API real a través del túnel ngrok real. Datos en bruto: [netlify-real.json](netlify-real.json).

| Id | Qué comprueba | Esperado | Observado | Estado |
|---|---|---|---|---|
| N1 | Carga desde Netlify | sin NG0900 ni errores; peticiones a la API por el túnel con CORS | sin errores de consola; `OPTIONS` y `GET` 200 a `/api/eventos`, `/api/estadisticas` y `/api/salud`; 164 eventos en mapa, 164 en tabla y total 164 en estadísticas ([captura](N1-netlify-load.png)) | SUPERADA |
| N2 | Reproducción desde Netlify | «REPRODUCCIÓN» en las cuatro zonas; datos aislados | etiqueta en estado, mapa, tabla y gráficos; «Mostrando 1000 de 2807»; estadísticas 2.807; al volver a modo real, 164 de 164 igual que antes ([captura](N2-netlify-replay.png)) | SUPERADA |
| N3 | **Cerrar y reabrir el túnel con el sitio de Netlify abierto** | aviso con la última lectura conservada; recuperación sin recargar | túnel parado: aviso a los 60 s (refresco de 60 s) con los 164 eventos conservados y la hora de la última lectura correcta; reabierto: «Datos al día» a los 56 s con datos nuevos (167 eventos), una sola navegación en toda la prueba ([cerrado](N3-netlify-tunnel-closed.png), [reabierto](N4-netlify-tunnel-reopened.png)) | SUPERADA |

Los únicos errores de CORS de consola aparecen mientras el túnel está cerrado (la página de «endpoint offline» de ngrok no lleva cabeceras CORS) y se tratan como backend inaccesible, como se espera.

## Prueba desde un dispositivo físico (2026-11-17)

Hecha por la persona autora con un **móvil Android y datos móviles** (otra red distinta de la del equipo) contra `https://seismicobservatoryecr.netlify.app`, sin recargar ni salir de la pestaña
(capturas con los botones físicos). El túnel lo paró y reabrió la sesión con `docker compose stop tunnel` y `docker compose --profile tunnel up -d tunnel`. Es la repetición limpia: un primer intento
no valió porque el navegador recargó la página sin querer (mostró «todavía no hay ninguna lectura correcta» y ND), y un segundo no se atribuye al túnel (no se había parado: ngrok seguía sirviendo 200) y no se usa.

| Id | Qué comprueba | Esperado | Observado | Estado |
|---|---|---|---|---|
| M1 | Estado inicial en el móvil | «Datos al día» | «Datos al día»; última lectura 15:30:22 UTC; 179 eventos ([captura](M1-mobile-before.jpg)) | SUPERADA |
| M2 | **Cerrar el túnel** (§11 prueba 9) | aviso de backend inaccesible; se conserva e identifica la última lectura | túnel parado a las 15:30:35 UTC; en el siguiente refresco: «Error: No se puede contactar con el backend. Se muestra la última lectura correcta» y «Aviso: los datos mostrados son la última lectura correcta, del 2026-11-17 15:30:22 UTC», con los 179 eventos en mapa y estadísticas ([captura](M2-mobile-tunnel-closed.jpg)) | SUPERADA |
| M3 | **Reabrir el túnel** (§11 prueba 10) | se recupera solo, sin recargar | túnel reabierto a las 15:31:33 UTC; el panel volvió a «Datos al día» con lectura de las 15:32:23 UTC (≈ 50 s) y 180 eventos ([captura](M3-mobile-tunnel-reopened.jpg)) | SUPERADA |

Contraste con ngrok (conector, inspector de tráfico, 2026-11-17, tramos de 30 s): 0 peticiones entre las 15:30:30 y las 15:31:30 UTC (túnel parado) y 3 por tramo antes y después.
