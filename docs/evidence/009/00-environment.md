# Entorno y estado base (spec 009)

Fecha: 2026-11-17. Equipo: Windows 11 (Git Bash), `DESKTOP-9149IE8`. Rama `009-dashboard-visual-redesign`.

| Elemento | Valor |
|---|---|
| Node | v24.22.1 |
| Angular CLI / Angular | 20.3.0 |
| Leaflet | 1.9.4 |
| Vitest | 3.2.7 |
| Estado base | `npm ci` y `npm test`: **106 pruebas en 8 ficheros, todas en verde** |

## Dependencias nuevas (versión exacta, sin `^`)

| Paquete | Versión | Licencia | Uso |
|---|---|---|---|
| `chart.js` | 4.6.1 | MIT | gráficos |
| `leaflet.markercluster` | 1.5.3 | MIT | agrupación |
| `leaflet.heat` | 0.2.0 | BSD-2-Clause | mapa de calor |
| `@types/leaflet.markercluster` (dev) | 1.5.6 | MIT | tipos |
| `@types/leaflet.heat` (dev) | 0.2.5 | MIT | tipos |

`npm run build` sigue en verde tras añadirlas (el aviso de Leaflet «not ESM» ya existía).

## Límites de placas

- Origen: `GeoJSON/PB2002_boundaries.json` de `fraxen/tectonicplates` (PB2002, P. Bird, 2003; datos de H. Ahlenius, Nordpil).
- Licencia: Open Data Commons Attribution License (ODC-By 1.0).
- Atribución: «Límites de placas: PB2002 (P. Bird, 2003); datos de H. Ahlenius, Nordpil».
- Fichero: `frontend/public/datos/placas.geojson`, 241 líneas, solo geometría y `Name`, 141.593 bytes, LF.
