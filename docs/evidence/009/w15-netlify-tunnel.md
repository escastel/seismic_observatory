# W15: túnel real y Netlify

Fecha: 2026-11-17. Estado: **PARCIAL**. Túnel real comprobado; **despliegue en Netlify no hecho**.

## Netlify: no desplegado

La usuaria autorizó el despliegue, pero este equipo no tiene la CLI de Netlify ni sesión iniciada (no hay `NETLIFY_AUTH_TOKEN` ni configuración de Netlify) y el proyecto no permite publicar mediante `git push` desde esta sesión. No se probó el sitio público `seismicobservatoryecr.netlify.app`. Para cerrarlo hay que publicar la compilación (`npm run build` en `frontend/`, carpeta `dist/observatorio/browser`) y repetir esta comprobación contra la URL pública.

## Túnel real de ngrok (con la compilación de producción servida en `http://localhost:4200`)

`config.json` del repositorio apunta al dominio reservado del túnel (`modular-guidance-daybreak.ngrok-free.dev`). Refresco acelerado a 5 s solo para la prueba. En bruto: [w15.json](w15.json).

| Comprobación | Esperado | Observado | Estado |
|---|---|---|---|
| Carga por el túnel | datos reales, sin errores | 212 eventos en tarjetas y tabla, «Al día», sin errores de aplicación ([captura](w15-tunnel-open.png)) | SUPERADA |
| Qué pasa por el túnel | solo la API | desde el navegador: `/api/eventos`, `/api/estadisticas` y `/api/salud` y nada más; 0 peticiones de teselas o placas al host del túnel. Las 18 teselas OSM y las 18 de Esri fueron directas a sus proveedores | SUPERADA |
| Inspector de tráfico de ngrok (conector) | solo rutas de la API | 12 peticiones en la ventana de la prueba, agrupadas por ruta: `/api/estadisticas` 4, `/api/eventos` 4, `/api/salud` 4; ninguna de teselas ni de `placas.geojson` | SUPERADA |
| Cerrar el túnel | aviso de backend inaccesible con la última lectura | 19:04:05 `docker compose stop tunnel`; a los 9 s: tarjeta «Backend inaccesible», «Se muestra la última lectura correcta», 212 eventos conservados ([captura](w15-tunnel-closed.png)) | SUPERADA |
| Reabrir el túnel | recuperación sin recargar | 19:04:16 `docker compose start tunnel`; en el refresco siguiente vuelve «Al día», 212 eventos, una sola navegación de página ([captura](w15-tunnel-reopened.png)) | SUPERADA |

Con Relieve y mapa de calor activados durante la prueba, el panel no pidió nada extra al túnel.
