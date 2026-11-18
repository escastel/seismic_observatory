# W15: túnel real y Netlify

Fecha: 2026-11-17. Estado: **SUPERADA**. Túnel real y sitio público de Netlify comprobados tras el merge a `main` (PR #10).

## Netlify (tras el merge a `main`, 2026-11-17 19:17 UTC)

Netlify publica al hacer merge a `main`. Sitio `https://seismicobservatoryecr.netlify.app` (título «seismicobservatory»; `datos/placas.geojson` responde 200). Navegador automatizado sobre la URL pública, API real a través del túnel ngrok real, refresco acelerado a 5 s solo para la prueba. En bruto: [w15-netlify.json](w15-netlify.json), [w15-netlify-smoke.json](w15-netlify-smoke.json).

| Comprobación | Observado | Estado |
|---|---|---|
| Carga desde Netlify | 208 eventos en tarjetas y tabla, «Al día», sin errores de consola ni de aplicación ([captura](w15n-tunnel-open.png)) | SUPERADA |
| Qué pasa por el túnel | solo `/api/eventos`, `/api/estadisticas` y `/api/salud`; 0 peticiones de teselas o placas al host del túnel (teselas OSM y Esri directas a sus proveedores) | SUPERADA |
| Inspector de tráfico de ngrok (conector) | 15 peticiones en la ventana: `/api/estadisticas` 5, `/api/eventos` 5, `/api/salud` 5; ninguna de teselas ni de `placas.geojson` | SUPERADA |
| Cerrar el túnel | 19:17:55 parado; a los 9 s «Backend inaccesible» con la última lectura y 208 eventos conservados ([captura](w15n-tunnel-closed.png)) | SUPERADA |
| Reabrir el túnel | 19:18:06 arrancado; en el refresco siguiente «Al día», 208 eventos, una sola navegación ([captura](w15n-tunnel-reopened.png)) | SUPERADA |
| Temas, capas y accesibilidad en el sitio público | fondo `rgb(11, 21, 32)` en oscuro y `rgb(238, 243, 246)` en claro; 5 tarjetas y 4 gráficos; calor (1 lienzo) y agrupación (10 grupos); axe 0 violaciones en ambos temas; sin desplazamiento horizontal a 390 px | SUPERADA |

## Antes del merge: túnel real de ngrok (con la compilación de producción servida en `http://localhost:4200`)

`config.json` del repositorio apunta al dominio reservado del túnel (`modular-guidance-daybreak.ngrok-free.dev`). Refresco acelerado a 5 s solo para la prueba. En bruto: [w15.json](w15.json).

| Comprobación | Esperado | Observado | Estado |
|---|---|---|---|
| Carga por el túnel | datos reales, sin errores | 212 eventos en tarjetas y tabla, «Al día», sin errores de aplicación ([captura](w15-tunnel-open.png)) | SUPERADA |
| Qué pasa por el túnel | solo la API | desde el navegador: `/api/eventos`, `/api/estadisticas` y `/api/salud` y nada más; 0 peticiones de teselas o placas al host del túnel. Las 18 teselas OSM y las 18 de Esri fueron directas a sus proveedores | SUPERADA |
| Inspector de tráfico de ngrok (conector) | solo rutas de la API | 12 peticiones en la ventana de la prueba, agrupadas por ruta: `/api/estadisticas` 4, `/api/eventos` 4, `/api/salud` 4; ninguna de teselas ni de `placas.geojson` | SUPERADA |
| Cerrar el túnel | aviso de backend inaccesible con la última lectura | 19:04:05 `docker compose stop tunnel`; a los 9 s: tarjeta «Backend inaccesible», «Se muestra la última lectura correcta», 212 eventos conservados ([captura](w15-tunnel-closed.png)) | SUPERADA |
| Reabrir el túnel | recuperación sin recargar | 19:04:16 `docker compose start tunnel`; en el refresco siguiente vuelve «Al día», 212 eventos, una sola navegación de página ([captura](w15-tunnel-reopened.png)) | SUPERADA |

Con Relieve y mapa de calor activados durante la prueba, el panel no pidió nada extra al túnel.
