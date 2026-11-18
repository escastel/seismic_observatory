# Implementation Plan: Rediseño visual y personalización del panel

**Branch**: `009-dashboard-visual-redesign` | **Date**: 2026-11-17 | **Spec**: `spec.md`

**Input**: Feature specification from `/specs/009-dashboard-visual-redesign/spec.md`

## Summary

Rediseño de la **presentación** del panel Angular de la 007, sin tocar la API (006) ni la lógica de datos: tema claro u oscuro según el dispositivo (oscuro por
defecto), selector de mapa base (simple, relieve con límites de placas, satélite) con variantes que siguen el tema, mapa de calor y agrupación como capas opcionales
etiquetadas como muestra, gráficos reales con tabla alternativa, tarjetas de resumen, ficha de evento propia, animaciones que respetan «reducir movimiento» e
identidad «seismicobservatory». Enfoque: tokens de diseño en CSS con `prefers-color-scheme`; lógica pura nueva en `lib/` con pruebas Vitest; componentes nuevos
o reescritos para mapa, gráficos, tarjetas y ficha; bibliotecas nuevas fijadas (Chart.js, leaflet.markercluster, leaflet.heat); todos los fondos **sin clave** y
cargados por el navegador directamente desde terceros, nunca por el túnel.

## Technical Context

**Language/Version**: TypeScript 5.9.2, Angular 20.3.0 (standalone, signals, OnPush), Node ≥ 22.12 (ya fijados en `frontend/package.json`).

**Primary Dependencies**: existentes: Leaflet 1.9.4, `@bluehalo/ngx-leaflet` 20.0.0, RxJS 7.8.2. **Nuevas, a fijar a versión exacta** (research R3 y R4): `chart.js` 4.6.1 (MIT),
`leaflet.markercluster` 1.5.3 (MIT) con `@types/leaflet.markercluster` 1.5.6, `leaflet.heat` 0.2.0 (BSD-2-Clause) con `@types/leaflet.heat` 0.2.5.

**Storage**: N/A (sin persistencia nueva; el tema sale del dispositivo). `localStorage` no se usa para estado que importe.

**Testing**: Vitest 3.2.7 para la lógica pura (`frontend/src/app/lib/*.test.ts`); navegador real con Puppeteer y axe-core (como en la 007) en ambos temas, escritorio y móvil,
y con «reducir movimiento»; comprobación con Netlify y el túnel (quickstart).

**Target Platform**: navegadores modernos de escritorio y móvil; SPA estática en Netlify; datos de la API vía ngrok.

**Project Type**: web (solo `frontend/`; sin cambios en `api/`, `db/`, `consumer/` ni `producer/`).

**Performance Goals**: utilizable en menos de 5 s en móvil con conexión normal (SC-007); las capas pesadas (relieve, placas, satélite, calor, agrupación) se cargan solo al elegirlas (carga diferida).

**Constraints**: sin claves ni credenciales en el frontend ni en Git (constitución, «Stack tecnológico y límites»); fondos de terceros sin clave; ninguna petición de fondos por el túnel
(cuota de 1 GB); contrato de la 006 intacto; contraste suficiente y no depender solo del color; texto de usuario siempre como texto.

**Scale/Scope**: hasta 1.000 eventos dibujados por petición (truncado de la API); 8.760 ventanas horarias como máximo en el análisis (la tabla las contiene todas; el gráfico dibuja una ventana, como hoy).

## Constitution Check

| Principio | Estado |
|---|---|
| I Arquitectura local | Sin servicios nuevos; no se publica nada más. OK |
| VI Aislamiento de la reproducción | La etiqueta «REPRODUCCIÓN» se mantiene en estado, mapa, tabla, gráficos y **también en tarjetas y ficha** (FR-019). OK |
| VII Analítica y comparación | Tarjetas y gráficos usan solo cifras de la API con periodo, filtros, unidad y sin valor; mapa de calor y agrupación rotulados «N de TOTAL». No se añade «magnitud máxima» calculada sobre la muestra. OK |
| VIII Contrato de la API | Sin cambios; el panel sigue consumiendo solo la 006 y distingue última lectura, generación e ingesta. OK |
| IX Evidencia ejecutada | Evidencia esperado/observado en `docs/evidence/009/`; pruebas de comportamiento, no de texto en el código. OK |
| Stack y límites | Bibliotecas nuevas solo si resuelven un requisito y fijadas: Chart.js (gráficos), markercluster (agrupación), leaflet.heat (calor). Credenciales: ninguna, se descartan los proveedores con clave (research R1). OK |
| Idioma | Código en inglés; textos del panel y documentación en español. OK |

Sin desviaciones. Tras el diseño se reevalúa: igual resultado.

## Project Structure

### Documentation (this feature)

```text
specs/009-dashboard-visual-redesign/
├── plan.md
├── research.md            # fuentes de mapa, licencias, bibliotecas, decisiones de diseño
├── data-model.md          # entidades de presentación (tema, capas, tarjetas, ficha)
├── quickstart.md          # escenarios de validación W1..W14
├── contracts/ui-contract.md
├── references/            # map-reference.png (guía de estilo), logo-proposal.svg (propuesta)
└── tasks.md               # /speckit-tasks
```

### Source Code (repository root)

```text
frontend/
├── public/
│   ├── datos/placas.geojson        # límites de placas PB2002 (ODC-By), cargado solo con el relieve
│   └── brand/ (logo.svg, favicon.svg)
├── src/
│   ├── index.html                  # título «seismicobservatory», favicon, meta theme-color
│   ├── styles.css                  # tokens de diseño claro/oscuro (prefers-color-scheme), base
│   └── app/
│       ├── theme/theme.service.ts  # señal `theme` (matchMedia), `reducedMotion`
│       ├── brand/logo.component.ts # logotipo «S» con onda sísmica (SVG, currentColor)
│       ├── summary/                # tarjetas de resumen (cifras de la API)
│       ├── event-card/             # ficha de evento accesible (diálogo/panel)
│       ├── map/                    # selector de fondos, capas calor/agrupación, placas, leyenda
│       ├── charts/                 # gráficos Chart.js + tablas alternativas
│       ├── status|filters|table/   # restyling; la lógica no cambia
│       └── lib/
│           ├── theme.ts            # resolver el tema (oscuro por defecto)
│           ├── map-layers.ts       # catálogo de fondos y capas, atribuciones, etiqueta de muestra
│           ├── summary.ts          # tarjetas desde Statistics + SystemStatus
│           ├── chart-series.ts     # series y colores desde las estadísticas (reutiliza chart-data.ts)
│           └── event-card.ts       # campos de la ficha (reutiliza format.ts y geo.ts)
```

**Structure Decision**: solo `frontend/`. La lógica nueva y comprobable vive en `lib/` sin Angular ni Leaflet (como en la 007); los componentes solo la enlazan.
No se modifican `observatory.service.ts`, `adapt.ts`, `api-types.ts`, `filters.ts` ni `status.ts` (FR-024).

## Complexity Tracking

Sin violaciones que justificar.
