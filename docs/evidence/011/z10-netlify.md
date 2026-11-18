# 011 · El panel de Netlify sigue funcionando (T019: Z10)

Panel `https://seismicobservatoryecr.netlify.app/` (el de `main`; la feature no toca el frontend), Chrome (Puppeteer), API real por el túnel **con la política de 60 por minuto activa**. Túnel cerrado y reabierto con `docker compose --profile tunnel stop|start tunnel`. Marca `window.__noReload` conservada: sin recargar la página. En bruto: [z10-netlify.json](z10-netlify.json); capturas `z10-*.png`. Ejecuté el guion tres veces (el primero con un país inexistente en el selector y el segundo para identificar los errores de consola); abajo, la última ejecución.

| Paso | Esperado | Observado |
|---|---|---|
| Carga | eventos reales | 196 eventos en mapa y tabla ([captura](z10-1-load.png)) |
| Albania | 0 eventos y aviso | 0 eventos, 0 filas, «Información: No hay eventos sísmicos ahora mismo en Albania» ([captura](z10-2-Albania.png)) |
| Estados Unidos | eventos del país | 148 eventos y filas, sin avisos ([captura](z10-3-Estados-Unidos.png)) |
| Quitar el filtro | todos otra vez | 197 eventos |
| Túnel cerrado + «Aplicar» | error con la última lectura | «No se puede contactar con el backend. Se muestra la última lectura correcta…»; siguen 197 eventos ([captura](z10-5-tunnel-closed.png)) |
| Túnel reabierto + «Aplicar», sin recargar | recuperación | «Conexión recuperada: los datos vuelven a actualizarse.»; 197 eventos ([captura](z10-6-tunnel-reopened.png)) |
| Respuestas de la API por el túnel (con el túnel abierto) | todas correctas | 22 × 200, ninguna otra |
| Errores de consola | ninguno con el túnel abierto | con el túnel **abierto**: ninguno de la API. Los únicos errores de CORS (3, `ERR_FAILED`) ocurren con el túnel **cerrado**, cuando responde la página de «offline» de ngrok sin cabeceras CORS: era esperable y el panel lo gestiona con el aviso anterior. Además 8 × `400` de `tile.openstreetmap.org` (teselas del mapa, no de nuestra API; causa no investigada) |

Nota: los 2 países probados fueron Albania y Estados Unidos (el selector usa los nombres en español). No se probó otro dispositivo ni la espera al refresco automático (se forzó con «Aplicar»).
