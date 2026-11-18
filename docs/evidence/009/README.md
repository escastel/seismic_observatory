# Evidencia spec 009: rediseño visual del panel

**Fecha**: 2026-11-17 · **Rama**: `009-dashboard-visual-redesign` · **Equipo**: Windows 11, Chrome headless (Puppeteer) contra la compilación de producción servida en `http://localhost:4200`, con la **API real local** (`http://localhost:8000`) salvo donde la fila lo indica.

Entorno, versiones y dependencias nuevas: [00-environment.md](00-environment.md). Las cifras de cada fila son del momento de su prueba (211 eventos en W1 a W7; 210 en W8 a W13).

Donde el sistema real no produce el caso, las respuestas se alteraron en el navegador por interceptación de peticiones (el repositorio y la base de datos no se tocaron). Resultados en bruto: [w-smoke.json](w-smoke.json), [w-extra.json](w-extra.json), [w-regression.json](w-regression.json), [w14-weight.json](w14-weight.json), [w15.json](w15.json), [w12-a11y.json](w12-a11y.json).

## Resultados

| Id | Qué comprueba | Esperado | Observado | Estado |
|---|---|---|---|---|
| W1 | Tema oscuro y claro | Oscuro con `prefers-color-scheme: dark`; claro con `light`; filtro CSS del mapa desactivado en claro | Oscuro: `body` `rgb(11, 21, 32)` ([captura](panel-dark.png)). Claro: [captura](panel-light.png); filtro del fondo Simple `none` ([w1-w7](w1-w7-theme-map.md)) | SUPERADA |
| W2 | Fondos Simple, Relieve y Satélite | Los tres cargan teselas | 12, 18 y 18 teselas cargadas; filtro oscuro solo en Simple y Relieve ([relieve](map-relief-dark.png), [satélite](map-satellite-dark.png)) | SUPERADA |
| W3 | Placas tectónicas con relieve | Activadas por defecto con Relieve; no se piden antes | `placas.geojson` no se pide al cargar; con Relieve la casilla está marcada y se pide ([captura](relief-plates.png)) | SUPERADA |
| W4/W5 | Mapa de calor y agrupación | Capas opcionales con rótulo de muestra | Con datos reales: calor 1 lienzo, agrupación 10 grupos y rótulo «Todos los eventos del periodo» (211 de 211) ([captura](map-heat-cluster-dark.png)). Con un periodo truncado simulado (total 2.500, 1.000 dibujados): rótulo «Muestra: 1000 de 2500» con el calor y con la agrupación; tras cargar todo con «Cargar más» (2.500 dibujados) pasa a «Todos los eventos del periodo» ([captura](w4-sample-label.png), [w4-sample.json](w4-sample.json)) | SUPERADA |
| W6 | Fallo de un fondo | Aviso y vuelta a Simple, eventos intactos | Con `arcgisonline.com` bloqueado: «No se pudo cargar el fondo «Relieve»; se vuelve al mapa Simple.»; 211 eventos dibujados | SUPERADA |
| W7 | Carga diferida | Chart.js, calor, agrupación y placas no se piden hasta usarlos | Al cargar solo se piden la aplicación, `paises.geojson`, teselas OSM y el trozo de gráficos; calor, agrupación y placas llegan al activarlos ([w1-w7](w1-w7-theme-map.md)) | SUPERADA |
| W8 | Tarjetas frente a la API | Cada cifra igual a `GET /api/estadisticas` con los mismos filtros | Seis casos (sin filtros; magnitud mínima 2; país USA + magnitud mínima 1; en oscuro y claro). Total de la API 210, 76 y 128; tarjeta «Eventos» igual en los seis; «Sin valor» 0 y 0 ([captura](w8-filtered-dark.png)) ([w8-w9](w8-w9-cards-charts.md)) | SUPERADA |
| W9 | Gráficos frente a la API | Tablas «por hora» y «por país» y eventos dibujados iguales al total de la API | En los seis casos, tabla «por hora», tabla «por país» y eventos dibujados iguales al total de la API (210, 76 y 128) ([w8-w9](w8-w9-cards-charts.md)). Distribución de magnitud y profundidad fila a fila no comprobada | SUPERADA |
| W10 | Ficha del evento | Nulos como «ND»; «Sin país asignado»; texto literal; coordenadas inválidas omitidas y contadas; 0 y negativos; foco y teclado; modo reproducción | Magnitud nula «ND» ([captura](w10-card-null-mag.png)); sin país «Sin país asignado»; texto con marcas literal, 0 elementos `img` o `b` en el diálogo; «208 eventos dibujados · 1 omitidos por coordenadas no válidas»; magnitud 0 «0,0 ml» y negativos «-0,5 ml» y «-1,2 km»; foco inicial en «Cerrar», Escape cierra, el foco vuelve al botón «Ver ficha» de la fila ([w10-w11](w10-w11-card-motion.md)) | SUPERADA |
| W11 | Movimiento reducido | Sin animación ni transición con `prefers-reduced-motion: reduce` | Ficha: `animation-name: none` y transición `0s`; tarjetas: `0s` ([w10-w11](w10-w11-card-motion.md)) | SUPERADA |
| W12 | Accesibilidad | axe-core WCAG 2.0/2.1 A y AA sin violaciones; ficha operable con teclado | 0 violaciones en oscuro y en claro ([w12-a11y.json](w12-a11y.json)); `card_closes_with_escape: true`; foco inicial en «Cerrar» | SUPERADA |
| W13 | No regresión de V1 a V15 de la 007 | Las pruebas V1 a V15 de la 007 pasan con el panel rediseñado | `npm test`: 13 ficheros, 142 pruebas en verde. V1, V3, V4, V5, V6, V7, V9, V10, V11, V12, V13, V14 y V15 SUPERADA. V2 PARCIAL. V8 NO REPETIDA ([captura reproducción](w13-replay.png), [sin conexión](w13-unreachable.png), [desactualizado](w13-stale.png)) ([w13-regression.md](w13-regression.md)) | PARCIAL |
| W14 | Móvil y peso | Sin desplazamiento horizontal a 390 px; utilizable en menos de 5 s con conexión normal (SC-007) | Ancho de página 390 = viewport tras corregir dos desbordes ([captura](mobile.png)). Primera tarjeta con datos 0,46 s (red normal) y 3,6 s (red lenta emulada); cuatro gráficos 1,6 s y 4,6 s. `main` 354 kB; Chart.js 202 kB diferido ([w14](w14-mobile-weight.md)) | SUPERADA |
| W15 | Túnel real y Netlify | Ninguna petición de teselas ni placas al túnel; cerrar y reabrir el túnel con recuperación sin recargar; sitio público de Netlify | Antes del merge (compilación local) y después en `seismicobservatoryecr.netlify.app`: carga con 208 eventos y «Al día»; solo `/api/eventos`, `/api/estadisticas` y `/api/salud` por el túnel (inspector de ngrok: 5 de cada); con el túnel parado, «Backend inaccesible» y 208 eventos conservados; reabierto, «Al día» sin recargar; axe 0 violaciones y sin desplazamiento horizontal en el sitio público ([w15](w15-netlify-tunnel.md)) | SUPERADA |
| W16 | Identidad y contraste | Logotipo aprobado por la usuaria; contraste medido de los colores de profundidad | Nombre, `<title>`, favicon y `theme-color` en oscuro y claro ([oscuro](panel-dark.png), [claro](panel-light.png)). Contraste de profundidad: 5,24:1 en oscuro y 3,67:1 en claro. **Logotipo aprobado** por la usuaria el 2026-11-17 ([w16](w16-identity.md)) | SUPERADA |

## Notas

- **W10, retorno del foco**: en la comprobación inicial de W1 a W7 quedó PARCIAL («el retorno del foco no se pudo comprobar»). En la de W10 y W11 se comprobó y figura SUPERADA; la tabla usa esta última.
- **W9**: solo se comparan totales y «sin valor» con la API, no la distribución de magnitud ni de profundidad fila a fila.

## Pendiente

- **V2 (W13)**: comprobar un evento nuevo real sin recargar; en la prueba no se esperó a un evento nuevo de USGS.
- **V8 (W13)**: repetir los filtros inválidos (inicio igual o posterior al fin; más de 10.000 horas).
- **Linux**: no consta en esta carpeta ninguna prueba en Linux; queda fuera de alcance por decisión de la usuaria (no es requisito del enunciado). `CLAUDE.md` sigue pidiendo que los cambios funcionen en ambos equipos.
