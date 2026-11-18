# X15. Peso y red (T033)

## Peso (compilación de producción, `npm run build`)

| | 009 (`w14-weight.json`) | 010 |
|---|---|---|
| `main` inicial | 354 KiB (≈ 362 kB) | 379,5 kB (101,7 kB transferidos) |
| Inicial total (con polyfills, estilos y chunk común) | — | 429,6 kB (116,8 kB transferidos) |
| Chunk de gráficos (carga diferida) | 202 KiB (≈ 207 kB) | 206,9 kB |
| Agrupación y calor (carga diferida, solo si se activan) | — | 34,4 kB y 4,9 kB |

El paquete principal crece unos 17 kB (≈ 5 %) por los componentes nuevos (barra, avisos, botón de tema, aviso emergente y lógica). No se añadió ninguna dependencia. La 009 midió la carga con tiempos y red limitada; aquí solo se compara el tamaño de los ficheros.

## Red por el túnel

Panel servido localmente (`ng serve`) con la `config.json` real (API por el túnel de ngrok). Recorrido: carga, activar calor, agrupación, fondo Satélite, filtrar por Albania. Datos del navegador en [x15-browser-hosts.json](x15-browser-hosts.json).

- Inspector de tráfico de ngrok (ventana del recorrido, agrupado por ruta): **11 peticiones, todas `/api/*`**: `/api/estadisticas` 4, `/api/eventos` 4, `/api/salud` 3.
- El navegador hizo 11 respuestas a `…ngrok-free.dev`, las mismas.
- Las teselas fueron directamente a `tile.openstreetmap.org` (24) y `tiles.maps.eox.at` (24); las fronteras y las placas son ficheros estáticos del propio panel. **Ninguna petición de teselas ni de placas pasó por el túnel.**
