# X16. Netlify y túnel (T036), 2026-11-18

Sitio público `https://seismicobservatoryecr.netlify.app/` (PR #11 ya desplegado), Chrome con Puppeteer, API real por el túnel de ngrok. El túnel se cerró y reabrió con `docker compose stop tunnel` y `docker compose start tunnel` (sin tocar volúmenes ni `.env`). En bruto: [x16-netlify.json](x16-netlify.json); capturas `x16-*.png`.

| Paso | Esperado | Observado |
|---|---|---|
| Carga | panel nuevo con la API real | título y cabecera «Seismic Observatory»; 192 eventos en mapa, barra y tabla, igual que `/api/estadisticas` (192); selector «Simple» y «Satélite»; placas marcadas; botón de tema presente; 0 errores de página |
| Albania | 0 eventos, aviso emergente y de información, nada del filtro anterior | 0 eventos y 0 filas; emergente y aviso «No hay eventos sísmicos ahora mismo en Albania» |
| Quitar el filtro | vuelven los eventos | 192 eventos |
| Túnel cerrado + «Aplicar» | error con la última lectura | «No se puede contactar con el backend. Se muestra la última lectura correcta…»; siguen 192 eventos y 192 filas |
| Túnel reabierto + «Aplicar», **sin recargar** (marca `window.__noReload` conservada) | datos otra vez, sin error | 192 eventos y sin avisos de error (el de «Conexión recuperada» caduca a los 8 s) |
| Red | solo `/api/*` por el túnel | el inspector de ngrok (ventana de la sesión, 146 peticiones) solo registra `/api/estadisticas` 50, `/api/eventos` 49 y `/api/salud` 47; las teselas fueron a `tile.openstreetmap.org` (18) |

**No repetido aquí**: el cierre y reapertura se forzó con «Aplicar» y no esperando al refresco automático de 60 s; sin otro dispositivo ni lector de pantalla.
