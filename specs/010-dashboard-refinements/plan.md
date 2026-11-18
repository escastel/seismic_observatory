# Implementation Plan: Ajustes de diseño, distribución y filtrado del panel

**Branch**: `010-dashboard-refinements` | **Date**: 2026-11-18 | **Spec**: `spec.md`

**Input**: Feature specification from `/specs/010-dashboard-refinements/spec.md`

## Summary

Refinamiento del panel de la 009 (ya en `main`) y una corrección de la API. Presentación: cabecera «Seismic Observatory», zona de **avisos** independientes por gravedad, una **barra de estado**
que sustituye al panel de estado y a las cinco tarjetas, **filtros** en una línea con título y chips, mapa primero con solo los fondos Simple y Satélite, placas activadas por defecto, calor con
degradado visible y **agrupación en burbujas**, y un **botón flotante de tema** (sol y luna) con elección manual recordada. Corrección: `GET /api/estadisticas` devuelve `period.end: null` cuando ningún
evento cumple el filtro (incumple el contrato de la 006); se corrige para devolver «ahora» y el panel pasa a tolerar un fallo solo de las estadísticas sin conservar la lectura de otro filtro, de modo
que filtrar por Albania deja el mapa y la tabla vacíos con un aviso. La lógica nueva va en `lib/` (Vitest) y la corrección de la API con una prueba de comportamiento (pytest).

## Technical Context

**Language/Version**: TypeScript 5.9.2, Angular 20.3.0 (standalone, signals, OnPush) en `frontend/`; Python 3.11 (FastAPI, asyncpg) en `api/`.

**Primary Dependencies**: sin dependencias nuevas. Existentes: Leaflet 1.9.4, `leaflet.markercluster` 1.5.3, `leaflet.heat` 0.2.0, Chart.js 4.6.1, Vitest 3.2.7, pytest 8.3.4. Se **retira** el fondo Relieve (sin
paquete propio: solo una URL y su atribución).

**Storage**: N/A. La preferencia de tema manual se guarda en `localStorage` con `try/catch` (comodidad individual de la persona; la página funciona sin ella).

**Testing**: Vitest para la lógica pura nueva (`lib/alerts`, `lib/status-bar`, `lib/filter-chips`, `lib/stats-tolerance`, `lib/cluster-style`, preferencia de tema, catálogo de capas); pytest en el contenedor `tests`
(`tests/query_api/test_statistics.py`) para la corrección de la API; navegador real con Puppeteer y axe-core como en la 007 y la 009. `tests/db` no se toca (nunca dos ejecuciones a la vez).

**Target Platform**: navegadores modernos de escritorio y móvil; SPA estática en Netlify (despliega al integrar en `main`); API local detrás de ngrok.

**Project Type**: web (`frontend/`) más un cambio mínimo en `api/app/stats.py`.

**Performance Goals**: sin regresión frente a la 009; el mapa visible en la primera pantalla (SC-001); carga diferida de las capas pesadas como hasta ahora.

**Constraints**: contrato de la 006 intacto (la corrección de `stats.py` hace cumplir el contrato, no lo cambia); sin credenciales en el frontend ni en Git; ninguna petición de teselas ni de placas por el túnel; texto de usuario siempre como texto; contraste suficiente
en ambos temas; los avisos no dependen solo del color.

**Scale/Scope**: hasta 1.000 eventos dibujados (truncado de la API); estadísticas sobre el conjunto completo.

## Constitution Check

| Principio | Estado |
|---|---|
| I Arquitectura local | Sin servicios nuevos. La API se reconstruye (`docker compose up --build -d api`). OK |
| VI Aislamiento de la reproducción | «REPRODUCCIÓN» sigue en estado, mapa, tabla, gráficos y ahora también en la barra de estado y en un aviso de información. OK |
| VII Analítica y comparación | Mapa, tabla y estadísticas aplican los mismos filtros **y un filtro sin eventos ya no deja datos de otro filtro**; las cifras de la barra salen de la API; calor y agrupación rotulados «N de TOTAL» y como «densidad de eventos de la muestra», nunca como peligrosidad. Mejora el cumplimiento. OK |
| VIII Contrato de la API | `period.end` pasa a ser siempre un número, como exige el contrato; no se añade ni cambia ningún campo. El panel sigue distinguiendo última lectura, generación e ingesta (en «Detalles») y avisando de datos desactualizados y de backend inaccesible. OK |
| IX Evidencia ejecutada | Prueba de comportamiento de la API y evidencia esperado/observado en `docs/evidence/010/`, incluido Albania con el sistema real. OK |
| Stack y límites | Sin bibliotecas nuevas; sin claves. OK |
| Idioma | Código en inglés; textos del panel y documentación en español. OK |

Sin desviaciones. El cambio en `api/app/stats.py` es el «cambio justificado» previsto por la spec 009/010 para un incumplimiento del contrato demostrado (research R1).

## Project Structure

### Documentation (this feature)

```text
specs/010-dashboard-refinements/
├── plan.md
├── research.md            # causa del fallo, decisiones de avisos, tema, mapa, barra, filtros
├── data-model.md          # entidades de presentación
├── quickstart.md          # escenarios X1..X16
├── contracts/ui-contract.md
├── references/            # mockup aprobado y comentarios de la persona autora
└── tasks.md               # /speckit-tasks
```

### Source Code (repository root)

```text
api/app/stats.py                              # corrección: period.end y period.start numéricos sin eventos (R1)
tests/query_api/test_statistics.py            # nueva prueba: sin eventos, periodo numérico y 24 ventanas
frontend/
├── src/
│   ├── index.html                            # <title> «Seismic Observatory»
│   ├── styles.css                            # tokens (data-theme), colores de avisos, estilos globales de burbujas de agrupación
│   └── app/
│       ├── app.component.*                   # nuevo orden: cabecera, avisos, barra, filtros, mapa, análisis, tabla; sin eyebrow ni tagline
│       ├── alerts/alerts.component.*         # zona de avisos (nuevo)
│       ├── status-bar/status-bar.component.* # barra de estado con «Detalles» (nuevo; sustituye a status/ y summary/)
│       ├── theme-toggle/theme-toggle.component.* # botón flotante sol/luna (nuevo)
│       ├── theme/theme.service.ts            # preferencia manual + dispositivo; atributo data-theme
│       ├── filters/filters.component.*       # una línea, título «Filtros», chips, plegado en móvil (lógica sin cambios)
│       ├── map/map.component.*               # solo Simple y Satélite, placas por defecto, calor visible, burbujas, controles y leyenda del mockup
│       ├── data/observatory.service.ts       # tolerancia: un fallo solo de estadísticas no descarta los eventos (R3)
│       ├── status/ y summary/                # se eliminan (sustituidos)
│       └── lib/
│           ├── alerts.ts                     # avisos desde estado, filtros, truncado, reproducción y capas
│           ├── status-bar.ts                 # métricas y detalles desde Statistics, lectura y estado (reutiliza summary.ts)
│           ├── filter-chips.ts               # chips de los filtros aplicados
│           ├── stats-tolerance.ts            # qué fallos de estadísticas conservan los eventos
│           ├── cluster-style.ts              # tamaño y color de la burbuja por recuento
│           ├── theme.ts                      # + resolvePreference(stored, deviceLight)
│           └── map-layers.ts                 # sin «relief»; placas activadas por defecto; degradado del calor
docs/evidence/010/                            # evidencia esperado/observado y capturas
```

**Structure Decision**: sin módulos nuevos fuera de `frontend/` salvo la corrección de una función de `api/app/stats.py` y su prueba. `adapt.ts`, `api-types.ts`, `filters.ts`, `status.ts` y `config.ts` no se modifican; el único cambio de la
lógica de datos de la 007 es en `observatory.service.ts` (tolerancia), documentado (FR-028).

## Complexity Tracking

Sin violaciones que justificar.
