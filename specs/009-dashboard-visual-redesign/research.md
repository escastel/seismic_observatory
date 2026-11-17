# Investigación (Fase 0)

Consultas hechas el 2026-11-17 (búsqueda web y peticiones reales de prueba a cada servicio de teselas). No quedan incógnitas sin resolver; lo que no se pudo
confirmar queda marcado como **riesgo** con su alternativa.

## R1. Proveedores de fondos: solo sin clave

- **Decisión**: usar únicamente servicios de teselas **sin clave de API**. Se descartan CARTO (Dark Matter y Positron), Stadia y MapTiler.
- **Razón**: la constitución prohíbe credenciales en el frontend y en Git. CARTO exige hoy una clave gratuita para sus teselas ráster (la documentación actual lo indica), así
  que su fondo oscuro «de fábrica» no es viable.
- **Alternativas**: CARTO con clave pública en el frontend (descartada: credencial en el cliente); estilos vectoriales con claves (descartada).

## R2. Fondos concretos (comprobados con peticiones reales, HTTP 200, con `Referer` del sitio de Netlify)

| Fondo | Origen de las teselas | Licencia y atribución | Notas |
|---|---|---|---|
| Simple claro | OpenStreetMap estándar (`tile.openstreetmap.org`, ya usado en la 007) | ODbL; «© OpenStreetMap contributors»; política de uso de teselas de la OSMF (uso moderado, `Referer`, sin precarga masiva) | |
| Simple oscuro | las mismas teselas de OSM con un **filtro CSS** (invertir, rotar el tono y atenuar) aplicado al panel de teselas | igual | Sin clave y sin servidor propio; el filtro se afina con capturas. **Riesgo**: el resultado es menos pulido que un estilo oscuro nativo |
| Relieve | **Esri World Shaded Relief** (`server.arcgisonline.com/ArcGIS/rest/services/World_Shaded_Relief/MapServer/tile/{z}/{y}/{x}`) | «Tiles © Esri — Source: Esri»; términos de uso de Esri (la metainformación del servicio los enlaza) | Servicio en «mature support» (sin actualizaciones). **Riesgo**: términos y disponibilidad; **alternativa**: la capa `terrain_3857` de EOX (verificar su licencia antes de usarla) |
| Relieve oscuro | el mismo relieve con filtro CSS (escala de grises, invertir, atenuar y tinte azul) | igual | Ajuste fino con la referencia visual |
| Satélite | **EOX Sentinel-2 cloudless 2021** (`tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2021_3857/default/g/{z}/{y}/{x}.jpg`) | CC BY-NC-SA 4.0 (versiones 2018–2021), WMTS gratuito para uso **no comercial** con atribución: «Sentinel-2 cloudless — https://s2maps.eu by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2021)» | El proyecto es académico y no comercial. **Riesgo**: las fuentes discrepan entre años; usar 2021 (la licencia está documentada) |

- Si un fondo no carga, el panel conserva el mapa simple y avisa (FR-007).
- Las teselas se piden **desde el navegador** al proveedor; no pasan por el túnel de ngrok ni por Netlify. Los proveedores ven la IP y el `Referer` del visitante: se declara en el pie de página.

## R3. Placas tectónicas

- **Decisión**: límites de placas **PB2002** (Bird, 2003) en la versión GeoJSON de `fraxen/tectonicplates` (`GeoJSON/PB2002_boundaries.json`: 241 líneas, 6.292 puntos, 226 kB; se recorta a la
  geometría y al nombre de cada límite).
- **Licencia**: Open Data Commons Attribution License (ODC-By 1.0), comprobada en el `LICENSE.md` del repositorio; atribución: «Límites de placas: PB2002 (P. Bird, 2003); datos de H. Ahlenius, Nordpil».
  Una fuente indica dominio público; se aplica la más restrictiva (ODC-By).
- **Entrega**: fichero estático `frontend/public/datos/placas.geojson` servido por Netlify (no por el túnel), cargado de forma diferida solo cuando se activa la capa.
- Se rotula como **«Límites de placas»**, no «fallas» (la referencia visual decía «fallas tectónicas»; los datos son de límites de placas).

## R4. Bibliotecas nuevas (verificadas en el registro de npm el 2026-11-17)

| Necesidad | Biblioteca | Versión fijada | Licencia | Razón |
|---|---|---|---|---|
| Gráficos | `chart.js` | 4.6.1 | MIT | Ligera con importación selectiva de controladores, sin envoltorio de Angular (menos riesgo de compatibilidad con Angular 20); el lienzo se complementa con tabla accesible |
| Agrupación | `leaflet.markercluster` (+ `@types/leaflet.markercluster` 1.5.6) | 1.5.3 | MIT | Estándar de Leaflet 1.9 |
| Mapa de calor | `leaflet.heat` (+ `@types/leaflet.heat` 0.2.5) | 0.2.0 | BSD-2-Clause | Mínima (≈ 3 kB), estándar; la 1.0.x existe pero 0.2.0 es la que acompañan los tipos |

- Las tres se importan **de forma diferida** (`import()`) cuando se usan, para no cargar peso inicial.
- **Alternativas descartadas**: ECharts (más pesada), `ng2-charts` (envoltorio adicional), SVG propio (más trabajo sin ventaja), un globo 3D (excluido por la usuaria).

## R5. Tema claro y oscuro

- **Decisión**: tokens de diseño como variables CSS en `styles.css`: el tema **oscuro es la base** y el claro se aplica bajo `@media (prefers-color-scheme: light)`; así, sin preferencia
  expresada, el panel es oscuro (FR-001). Una señal de Angular (`matchMedia`) informa de la preferencia a mapa y gráficos para que cambien sin recargar.
- `color-scheme` se declara para controles nativos; `meta theme-color` por tema.
- **Alternativa descartada**: conmutador manual con `localStorage` (no pedido; podría añadirse luego).

## R6. Mapa de calor y agrupación sobre la muestra

- La API entrega como mucho 1.000 eventos por petición y `metadata.total` con el total real. La capa activa muestra «Muestra: N de TOTAL» cuando `N < TOTAL` y, si coincide con el total, «Todos los eventos del periodo».
- El mapa de calor pondera por magnitud (peso = magnitud normalizada); sin magnitud, peso mínimo, nunca cero ni valor inventado.
- La agrupación muestra el recuento por grupo y no oculta los eventos sin coordenadas válidas (se siguen contando aparte, como hoy).

## R7. Gráficos accesibles

- Cada gráfico lleva `role="img"` con `aria-label` (título, periodo, filtros, unidad, sin valor) y, debajo, la tabla de datos existente en `<details>` («Ver tabla de datos»), que conserva las filas completas.
- Los colores salen de los tokens (misma paleta de profundidad que el mapa); se evita depender solo del color con etiquetas y valores en la tabla.
- Al cambiar el tema se reconstruyen los colores del gráfico; con `prefers-reduced-motion` se desactivan las animaciones de Chart.js.

## R8. Ficha del evento

- **Decisión**: componente propio (panel lateral en escritorio y hoja inferior en móvil) con `role="dialog"`, foco gestionado, cierre con Escape y con botón; se abre desde el mapa
  (clic en un círculo o en un grupo) y desde la tabla (botón «Ver ficha» en cada fila). Usa los datos que ya tiene el panel; **no hace peticiones nuevas**.
- Texto siempre por interpolación de Angular (nunca HTML) (FR-016).
- Sustituye al globo de texto de Leaflet; las animaciones solo si `prefers-reduced-motion: no-preference`.

## R9. Identidad

- Nombre «seismicobservatory»; logotipo: una «S» con una decoración de onda sísmica (línea de sismograma que atraviesa la letra), en SVG de un solo color (`currentColor`) con variante de
  acento. Propuesta en `references/logo-proposal.svg` para su aprobación (FR-018: provisional hasta entonces).
- Tipografía: pila del sistema (`system-ui`) para el texto y una monoespaciada del sistema para cifras; no se cargan fuentes externas (sin peticiones ni peso extra). **Alternativa**: una fuente
  propia autoalojada con licencia abierta si la usuaria lo pide.
- Paleta: tokens oscuros y claros (fondo, superficie, texto, acento, estados), profundidad: amarillo, naranja y morado de la referencia, ajustados para contraste en ambos temas.

## R10. Qué no cambia (comprobación de no regresión)

`observatory.service.ts`, `adapt.ts`, `api-types.ts`, `filters.ts`, `status.ts` y `config.ts` no se modifican; sus pruebas (106 en 8 ficheros) deben seguir en verde; los escenarios V1 a V15 de la 007 se repiten (W13).

## R11. Orquestación

Sesión principal: tokens de tema, selector de capas, integración, navegador real, evidencias y memoria. Sonnet: lógica pura con sus pruebas y componentes (gráficos, tarjetas, ficha, logotipo).
Haiku: documentación a partir de la evidencia. Cada agente toca solo los ficheros de su tarea; ninguno hace commit.
