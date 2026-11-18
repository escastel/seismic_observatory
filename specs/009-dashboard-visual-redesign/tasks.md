---

description: "Task list for feature 009: dashboard visual redesign and personalization"
---

# Tasks: Rediseño visual y personalización del panel

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/ui-contract.md](contracts/ui-contract.md), [quickstart.md](quickstart.md)

**Tests**: incluidas (principio IX, FR-027). Pruebas de comportamiento de la lógica pura en `frontend/src/app/lib/*.test.ts` (Vitest): comprueban resultados de funciones, nunca la presencia de
texto en el código. Lo visual se comprueba en navegador real (quickstart W1 a W16).

**Reglas**: código, nombres y comentarios en inglés; textos visibles y documentación en español. LF. Nunca leer ni imprimir `.env`; no ejecutar `docker compose config`. Sin cambios en `api/`,
`db/`, `consumer/` ni `producer/`, y **sin tocar** `observatory.service.ts`, `adapt.ts`, `api-types.ts`, `filters.ts`, `status.ts` ni `config.ts` (FR-024). Versiones nuevas fijadas **exactas** (sin `^`).
Sin claves ni credenciales en el frontend ni en Git. Texto de usuario siempre como texto, nunca HTML. Ninguna petición de teselas ni de placas por el túnel. `docker compose down -v` pide
confirmación explícita. **Desplegar a Netlify (publica el panel) pide confirmación explícita.** Nunca dos ejecuciones de `tests/db` a la vez (no se tocan en esta spec).

**Agentes** (etiqueta `[A#]`, norma «Orquestación de agentes» de `CLAUDE.md`):

- `[A0]` sesión principal: tokens, integración en `app.component`, Leaflet y capas, todo lo que toca el sistema real (Docker, navegador, Netlify, ngrok), evidencias, memoria y commit.
- `[A1]` agente nuevo en segundo plano, **Sonnet**: lógica pura de `lib/` con sus pruebas y componentes autocontenidos.
- `[A2]` agente nuevo en segundo plano, **Haiku**: documentación a partir de la evidencia ya guardada (nunca inventa cifras).

Cada agente recibe un prompt corto que apunta a este fichero y a los contratos (nunca `fork`), solo toca los ficheros listados en su tarea y no hace commit. Dos agentes a la vez solo si sus ficheros
no se solapan. Los agentes de `frontend/` ejecutan solo `npm test` de sus ficheros (`npx vitest run <fichero>`); la sesión principal ejecuta la suite completa y la compilación una vez.

## Format: `[ID] [P?] [Story] [A#] Descripción con ficheros`

---

## Phase 1: Setup

- [X] T001 [A0] Comprobar la rama `009-dashboard-visual-redesign` y `.specify/feature.json`; ejecutar `npm ci` y `npm test` en `frontend/` y guardar el estado base (106 pruebas en 8 ficheros, versiones de Node, Angular y Leaflet, equipo) en `docs/evidence/009/00-environment.md`
- [X] T002 [A0] Añadir a `frontend/package.json` con versión **exacta** `chart.js` 4.6.1, `leaflet.markercluster` 1.5.3, `leaflet.heat` 0.2.0 y, como dev, `@types/leaflet.markercluster` 1.5.6 y `@types/leaflet.heat` 0.2.5; actualizar `package-lock.json`; `npm ci` y `npm run build` siguen en verde (research R4)
- [X] T003 [A0] Descargar `GeoJSON/PB2002_boundaries.json` de `fraxen/tectonicplates`, conservar solo geometría y `Name` y guardarlo como `frontend/public/datos/placas.geojson` (≈ 150–226 kB, LF); anotar origen, licencia ODC-By y atribución en `docs/evidence/009/00-environment.md` (research R3)

---

## Phase 2: Foundational (bloquea las historias)

- [X] T004 [A0] Reescribir `frontend/src/styles.css` con los tokens de diseño: tema **oscuro como base** y claro bajo `@media (prefers-color-scheme: light)`, `color-scheme`, escala tipográfica del sistema, espaciados, foco, y regla `@media (prefers-reduced-motion: reduce)` que anula transiciones (contrato §1, §6)
- [X] T005 [P] [A1] Crear `frontend/src/app/lib/theme.ts` (`resolveTheme(prefersLight: boolean | null): 'dark' | 'light'`, oscuro por defecto si es `null` o `false`; `reducedMotion`), su prueba `lib/theme.test.ts` y `frontend/src/app/theme/theme.service.ts` (señales `theme` y `reducedMotion` con `matchMedia` que cambian sin recargar); sin tocar otros ficheros (data-model: Theme)
- [X] T006 [P] [A1] Crear `frontend/src/app/lib/map-layers.ts` y `lib/map-layers.test.ts`: catálogo de fondos `simple`, `relief`, `satellite` (`tiles(theme)`, `filter(theme)`, `attribution`, `maxZoom`) con las URL y atribuciones de `research.md` R2, capas opcionales `heat`, `cluster`, `plates`, y `sampleLabel(drawn, total)` («Muestra: N de TOTAL» si N < TOTAL, «Todos los eventos del periodo» si N = TOTAL); sin importar Leaflet ni Angular (data-model: BaseLayer, OverlayLayer)
- [X] T007 [P] [A1] Crear `frontend/src/app/lib/summary.ts` y `lib/summary.test.ts`: las cinco `SummaryCard` (total, última ingesta, estado, periodo, sin valor) a partir de `Statistics`, el estado del panel y `Reading` ya existentes; `ND` sin dato; etiqueta «REPRODUCCIÓN»; **sin** tarjeta de magnitud máxima ni cifras de la muestra del mapa (data-model: SummaryCard)
- [X] T008 [P] [A1] Crear `frontend/src/app/lib/chart-series.ts` y `lib/chart-series.test.ts`: `ChartSeries` (`hourly`, `country`, `magnitude`, `depth`) reutilizando `lib/chart-data.ts` sin modificarlo, con título, unidad, periodo, filtros, sin valor, colores por tema (profundidad igual que `geo.ts`) y filas de tabla completas; «Sin país asignado» como una fila más (data-model: ChartSeries)
- [X] T009 [P] [A1] Crear `frontend/src/app/lib/event-card.ts` y `lib/event-card.test.ts`: campos de la ficha desde un `MapEvent` y el modo, reutilizando `format.ts` y `geo.ts`; `ND`, «Sin país asignado», magnitudes y profundidades negativas con su valor, texto con marcas devuelto tal cual (data-model: EventCard)

**Checkpoint**: tokens y lógica pura verificadas con Vitest; nada visual aún.

---

## Phase 3: User Story 1 - Tema y mapas base (Priority: P1) 🎯 MVP

**Goal**: tema claro/oscuro del dispositivo y mapa con fondos y capas.

**Independent Test**: W1 a W7.

- [X] T010 [US1] [A0] Reescribir `frontend/src/app/map/map.component.ts` (y `.html`, `.css`): selector de fondo accesible (Simple, Relieve, Satélite) con el catálogo de T006, variante clara u oscura según `theme()` (filtro CSS sobre el panel de teselas), círculos actuales por magnitud y profundidad sin cambios de lógica, fallo de teselas con aviso y vuelta a Simple (FR-003, FR-007, FR-008)
- [X] T011 [US1] [A0] En `map/map.component.ts`: capas opcionales mapa de calor (`leaflet.heat`, peso por magnitud, mínimo sin magnitud), agrupación (`leaflet.markercluster`, sustituye a los círculos sueltos) y límites de placas (`placas.geojson`, línea discontinua, activada por defecto solo con Relieve), todas con `import()` diferido; rótulo de muestra con `sampleLabel` (FR-004, FR-005, FR-025)
- [X] T012 [US1] [A0] En `map/map.component.*`: leyenda (profundidad, tamaño, ND, calor y placas), atribuciones visibles del fondo y de las capas activas, región `role="status"` para avisos y estilo del selector con los tokens (contrato §2)
- [X] T013 [US1] [A0] Integrar en `frontend/src/app/app.component.ts|html|css`: inyectar `ThemeService`, pasar `theme` y `metadata.total` al mapa, pie de página con atribuciones (OSM, Esri, EOX, PB2002, Natural Earth, USGS) y la nota de que los proveedores de teselas ven la IP y el `Referer`
- [X] T014 [US1] [A0] Verificar W1 a W7 en navegador real (Puppeteer con emulación de `prefers-color-scheme`, fondos, capas, fallo de dominio bloqueado); guardar capturas y JSON en `docs/evidence/009/w1-w7-theme-map.md`

**Checkpoint**: US1 verificable por sí sola.

---

## Phase 4: User Story 2 - Gráficos y tarjetas (Priority: P1)

**Goal**: gráficos reales con tabla y tarjetas de resumen.

**Independent Test**: W8 y W9.

- [X] T015 [P] [US2] [A1] Reescribir `frontend/src/app/charts/charts.component.ts|html|css` con Chart.js (importación selectiva y diferida de controladores y escalas): cuatro gráficos desde `chart-series`, colores del tema, `role="img"` con descripción, tabla en «Ver tabla de datos» (`<details>`), aviso de ventanas ocultas, etiqueta «REPRODUCCIÓN», animaciones solo con `reducedMotion` falso; mismos `input()` que hoy (`statistics`, `statsFailure`, `label`) más `theme`
- [X] T016 [P] [US2] [A1] Crear `frontend/src/app/summary/summary.component.ts|html|css`: tarjetas de resumen (T007) con cifras grandes, unidad, filtros y sin valor; estado con icono y texto, no solo color
- [X] T017 [US2] [A0] Integrar tarjetas y gráficos en `app.component.html|ts|css` (cabecera con tarjetas bajo el título; gráficos tras el mapa) y pasar `theme`; conservar `app-status` con sus avisos y regiones `aria-live`
- [X] T018 [US2] [A0] Verificar W8 y W9 comparando cada cifra con `GET /api/estadisticas` en tres conjuntos de filtros, ambos temas y modo reproducción; evidencia en `docs/evidence/009/w8-w9-cards-charts.md`

---

## Phase 5: User Story 3 - Ficha del evento y animaciones (Priority: P2)

**Independent Test**: W10 y W11.

- [X] T019 [P] [US3] [A1] Crear `frontend/src/app/event-card/event-card.component.ts|html|css`: diálogo (`role="dialog"`, `aria-modal`, título, foco inicial en el botón de cierre, retorno del foco, Escape), panel lateral en escritorio y hoja inferior en móvil, campos de `lib/event-card.ts`, texto solo por interpolación, transición solo con `reducedMotion` falso; `input()` del evento y del modo, `output()` de cierre
- [X] T020 [US3] [A0] Cablear la ficha: clic en un círculo o en un grupo del mapa (`map.component.ts`: `output()` del evento elegido), botón «Ver ficha» en cada fila de `table/table.component.html|ts` y estado en `app.component.*`; sustituir el globo de Leaflet; animaciones suaves (apertura de la ficha, cambio de capa) solo con movimiento permitido (FR-014, FR-015)
- [X] T021 [US3] [A0] Verificar W10 y W11 (evento sin país, valores nulos y texto con marcas con el simulador de contrato de la 007; foco y Escape; `prefers-reduced-motion: reduce`); evidencia en `docs/evidence/009/w10-w11-card-motion.md`

---

## Phase 6: User Story 4 - Identidad (Priority: P2)

**Independent Test**: W16.

- [X] T022 [P] [US4] [A1] Crear `frontend/src/app/brand/logo.component.ts` (SVG «S» con onda sísmica de `specs/009-dashboard-visual-redesign/references/logo-proposal.svg`, con `currentColor` y acento por token), `frontend/public/brand/logo.svg` y `favicon.svg`, y actualizar `frontend/src/index.html` (`<title>` «seismicobservatory», favicon, `meta theme-color` por tema)
- [X] T023 [US4] [A0] Componer la cabecera en `app.component.html|css` con el logotipo, el nombre «seismicobservatory» y las tarjetas; paleta y tipografía propias coherentes en ambos temas (FR-017, FR-018)
- [X] T024 [US4] [A0] Verificar W16 y el contraste de los colores de profundidad en ambos temas; evidencia en `docs/evidence/009/w16-identity.md`

---

## Phase 7: User Story 5 - Nada de lo verificado se pierde (Priority: P1)

**Independent Test**: W12 a W15.

- [X] T025 [P] [US5] [A1] Adaptar a los tokens solo el CSS de `frontend/src/app/status/status.component.css`, `filters/filters.component.css` y `table/table.component.css` (colores, superficies, foco, estados claro/oscuro y móvil); sin tocar HTML, TypeScript ni lógica
- [X] T026 [US5] [A0] Accesibilidad (W12): axe-core WCAG A y AA en claro y oscuro, recorrido con teclado, foco visible, contraste; corregir lo que salga y guardar `docs/evidence/009/w12-a11y.json`
- [X] T027 [US5] [A0] No regresión (W13): `npm test` completo (las 106 pruebas anteriores más las nuevas), repetir V1 a V15 de la 007 con el panel rediseñado (API real y simulador), cierre y reapertura del túnel con el simulador; `git diff 008-analysis-costs-deliverables` vacío en los ficheros que no se pueden tocar; evidencia en `docs/evidence/009/w13-regression.md`
- [X] T028 [US5] [A0] Móvil y peso (W14): viewport de móvil, red lenta emulada, `npm run build`; medir peso inicial y comprobar carga diferida de Chart.js, calor, agrupación, placas y teselas; evidencia en `docs/evidence/009/w14-mobile-weight.md`
- [X] T029 [US5] [A0] **Pedir confirmación**, desplegar a Netlify y repetir en el sitio real con el túnel (W15): cerrar y reabrir el túnel; con el conector de ngrok comprobar que no hay peticiones de teselas ni de placas en el inspector de tráfico; evidencia en `docs/evidence/009/w15-netlify-tunnel.md`

---

## Phase 8: Polish y cierre

- [X] T030 [P] [A2] Con la evidencia de `docs/evidence/009/`, redactar `docs/evidence/009/README.md` (resumen de W1 a W16 con esperado/observado y estado, capturas enlazadas) sin inventar cifras
- [X] T031 [A0] Añadir a `docs/report.md` el apartado «Panel rediseñado (spec 009)» (decisiones, fuentes y licencias de fondos y placas, bibliotecas, límites, evidencia), actualizar el índice y la nota de `README.md` sobre el panel; revisar enlaces
- [X] T032 [A0] Actualizar la memoria del proyecto (`MEMORY.md` y fichero de estado de la 009), revisar `git status` y hacer commit sin `git add -A`; sin push

---

## Dependencias

- Setup → Foundational (T004 y T005 a T009 en paralelo) → US1 (secuencial: T010 a T013 tocan los mismos ficheros) → US2 → US3 → US4 → US5 → Polish.
- T015 y T016 en paralelo (ficheros distintos); T017 espera a ambos y a T013 (mismo `app.component`). T019 y T022 pueden ir en paralelo con trabajo de la sesión principal si sus ficheros no se solapan. T025 (solo CSS) es independiente de T020 (HTML y TS de la tabla).
- T029 exige confirmación explícita antes de desplegar.

## Estrategia

MVP: Phases 1–3 (tema y mapas base). Después gráficos y tarjetas, la ficha, la identidad y las comprobaciones. Una historia por sesión si se agota el contexto.

## Resumen

32 tareas: Setup 3, Foundational 6, US1 5, US2 4, US3 3, US4 3, US5 5, Polish 3.
