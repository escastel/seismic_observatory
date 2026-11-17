# W14: móvil y peso

Fecha: 2026-11-17. Chrome headless, viewport de móvil 390 × 800 con pantalla táctil, caché desactivada, compilación de producción servida sin compresión por un servidor estático local contra la API real local. En bruto: [w14-weight.json](w14-weight.json).

| Medida | Red normal | Red lenta (1,6 Mbit/s, 150 ms) |
|---|---|---|
| Hasta la primera tarjeta con datos | 0,46 s | 3,6 s |
| Hasta la primera tesela del mapa | 0,53 s | 3,6 s |
| Hasta los cuatro gráficos | 1,6 s | 4,6 s |

SC-007 (utilizable en menos de 5 s en móvil con conexión normal): se cumple, también con la red lenta emulada.

| Carga inicial (sin compresión) | kB |
|---|---|
| `main` (aplicación) | 354 |
| Chart.js (trozo diferido, se pide al pintar los gráficos) | 202 |
| `paises.geojson` (de la 007, no nuevo) | 819 |
| API (eventos, estadísticas, salud) | 73 |
| Teselas del mapa Simple | 27 |

`npm run build` informa de **410,65 kB** iniciales sin comprimir (112,16 kB comprimidos) y de tres trozos diferidos: Chart.js (206,86 kB; 61,82 kB comprimidos), agrupación (34,38 kB) y calor (4,88 kB). El tamaño comprimido de Netlify no se midió en el sitio real.

- **Carga diferida**: al cargar solo se piden la aplicación, `paises.geojson`, las teselas OSM y el trozo de Chart.js. Los trozos de calor y agrupación, `placas.geojson` y las teselas de relieve o satélite se piden solo al elegirlos ([W1–W7](w1-w7-theme-map.md)).
- **Sin desplazamiento horizontal** a 390 px (ancho de página 390 = viewport), tras corregir dos desbordes ([captura](mobile.png)).
- El elemento más pesado, `paises.geojson`, ya estaba en la 007; reducirlo queda fuera de esta spec.
