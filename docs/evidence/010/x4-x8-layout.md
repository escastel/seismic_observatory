# X4, X5, X7 y X8. Distribución (T020)

Sistema real (API local, `ng serve`, Chrome con Puppeteer). Mediciones en [x4-layout.json](x4-layout.json) y [x5-bar-vs-api.json](x5-bar-vs-api.json).

| Comprobación | Esperado | Observado |
|---|---|---|
| X4 cabecera | «Seismic Observatory» con «Seismic» en acento, sin antetítulo ni lema, ambos temas; título de pestaña igual | h1 y `document.title` = «Seismic Observatory»; sin `.eyebrow` ni `.tagline`; capturas `x4-desktop-dark.png`, `x4-desktop-light.png` |
| X7 primera pantalla 1440×900 | mapa a la vista | barra 98–179 px, filtros 199–410 px, mapa desde 470 px (de 900) |
| X7 móvil 390×844 | mapa a la vista, sin desbordes | mapa desde 361 px; `overflowX` falso; `x4-mobile-full.png` |
| X5 barra vs `/api/estadisticas` | mismas cifras | sin filtro 202 = 202; magnitud ≥ 5: 10 = 10; país JPN: 0 = 0 |
| X5 «Detalles» | despliega última lectura, generación, ingesta, cuarentena, sin magnitud | `aria-expanded="true"` y las seis líneas (`x4-desktop-dark-details.png`) |
| X8 filtros | una línea con título «Filtros», chips de los aplicados | una fila (controles y botones) a 1440 px; chips: Modo, Periodo, magnitud, país; en móvil botón «Filtros» y chips visibles, formulario desplegable (`x4-mobile-filters-open.png`) |

**Ajustes hechos tras la primera captura** (no cumplía): los controles no cabían en una línea; los valores de la barra salían truncados y la barra crecía; los controles del mapa tapaban media pantalla en móvil. Se acortaron los valores de la barra (`lib/status-bar.ts`, con pruebas: «Últimas 24 h», hora de la ingesta, «0 · 0»; el texto completo queda en el detalle y en «Detalles»), se compactaron filtros y controles del mapa y en móvil se ocultan las unidades de la barra.

**Observado, no corregido**: la unidad de «Eventos» sale como «events» porque es el valor `unit` que devuelve la API (comportamiento de la 009).
