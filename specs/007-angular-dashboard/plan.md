# Implementation Plan: Panel Angular conforme al enunciado

**Branch**: `007-angular-dashboard` | **Date**: 2026-11-16 | **Spec**: `spec.md`

**Input**: Feature specification from `/specs/007-angular-dashboard/spec.md`

## Summary

El panel entregado (`frontend/`, un único componente de unas 150 líneas) se revisa y se adapta, no
se reescribe desde cero: se conservan Angular 20.3, ngx-leaflet 20.0.0, Leaflet 1.9.4, el mapa con
capas independientes, `paises.geojson`, `netlify.toml` y la lectura de `config.json`. Lo que cambia
es la capa de datos y la presentación, porque hoy el panel lee el formato antiguo de la API.

Decisiones de diseño (detalle en [research.md](research.md)):

- **Lógica pura separada de la interfaz** en `frontend/src/app/lib/` (adaptación de respuestas,
  formato de nulos y fechas, construcción de parámetros, derivación del estado). Es lo que se prueba
  con pruebas de comportamiento (Vitest, fijado) sin navegador.
- **Una sola petición de filtros**: un objeto `QueryFilters` produce los parámetros de
  `/api/eventos` y de `/api/estadisticas`; mapa, tabla y gráficos nacen de él (principio VII).
- **Un servicio de lectura con un ciclo de refresco**: una petición cada vez (sin solapes), tiempo
  máximo 15 s, secuencia por consulta para descartar respuestas tardías, y última lectura correcta
  conservada y rotulada cuando falla una nueva.
- **El estado se deriva, no se escribe a mano**: una función pura convierte (lectura, error,
  salud, reloj) en uno de los estados de la spec (normal, desactualizado, degradado, inaccesible,
  parámetros inválidos, base no disponible, sin eventos).
- **Modo en el cliente = modo en la petición**: cambiar de modo cancela lo pendiente, vacía mapa,
  tabla y gráficos y exige que la respuesta traiga el mismo `metadata.mode` (y, en `replay`, la
  etiqueta). Demo retirado.
- **Catálogo de países desde `paises.geojson`** (`ADM0_A3` = `country_id` de la base, comprobado en
  `consumer/app/spatial.py`): sin servicio nuevo.
- **Gráficos en SVG/HTML propio, sin biblioteca**, cada uno acompañado de su tabla de valores.
- **Tabla con paginación por `next_offset`** («Cargar más»), con `count` frente a `total`.

Sin cambios en la API (CORS y contrato de la 006 ya bastan; se verifica en la evidencia). Sin
dependencias de ejecución nuevas; una de desarrollo (Vitest, versión exacta).

## Technical Context

**Language/Version**: TypeScript 5.9.2 (estricto); Node ≥22.12 <23 o ≥24 <25 (`engines` ya fijado)

**Primary Dependencies**: Angular 20.3.0, @bluehalo/ngx-leaflet 20.0.0, Leaflet 1.9.4, RxJS 7.8.2
(ya fijadas, sin cambios). Nueva solo de desarrollo: `vitest` en versión exacta (se fija en la
primera tarea tras comprobar la última estable ≥ 2 semanas)

**Storage**: N/A (sin almacenamiento propio; `localStorage` no se usa para estado de datos)

**Testing**: Vitest sobre `src/app/lib/` (comportamiento de lógica pura); comprobación en navegador
real con la API de la 006 levantada (skill `verify-stack`), evidencia en `docs/evidence/007/`

**Target Platform**: navegadores modernos (escritorio y móvil); build estático publicado en
Netlify; desarrollo en Windows 11 (Git Bash) y Linux

**Project Type**: SPA web que consume una API ya existente (web application, solo frontend)

**Performance Goals**: mapa y tabla con datos en menos de 5 s desde la apertura (SC-001); 1.000
círculos en lienzo (`preferCanvas`) sin bloquear la interfaz

**Constraints**: solo `GET` a `/api/eventos`, `/api/estadisticas`, `/api/salud`; nunca USGS;
cabecera `ngrok-skip-browser-warning` configurable; sin secretos; texto siempre como texto (nunca
HTML); textos en español, código en inglés; LF

**Scale/Scope**: una pantalla con mapa, tabla, cuatro gráficos y panel de estado; hasta decenas de
miles de filas recorribles por paginación; un componente raíz dividido en componentes pequeños

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación | Estado |
|---|---|---|
| I. Superficie mínima | Netlify solo publica la SPA; backend local tras túnel; sin Functions ni servicios nuevos; sin secretos en el panel. | Cumple |
| II. Idempotencia | Cada refresco sustituye la capa y la tabla completas; sin acumulación ni duplicados. | Cumple |
| III. Calidad | Nulos como ND, nunca 0, `undefined` ni `NaN`; coordenadas no válidas omitidas y contadas; cuarentena visible desde `metadata.quarantined`. | Cumple |
| IV. Espacial | `country_id`/`country_name` tal cual; «Sin país asignado» visible en ficha, tabla y análisis. | Cumple |
| V. Original y procedencia | Se muestran los tres instantes (lectura, `generated`, `last_ingestion`) sin mezclarlos. | Cumple |
| VI. Aislamiento | Etiqueta «REPRODUCCIÓN» de `metadata.label` en todas las vistas; cambio de modo limpia todo; respuesta de modo distinto o sin etiqueta rechazada. | Cumple |
| VII. Analítica | Estadísticas de la API (nunca recalculadas en cliente), mismos filtros para las tres vistas, periodo/filtros/unidad/sin valor visibles, ND y aviso de periodo incompleto. | Cumple |
| VIII. Contrato | El panel solo habla el contrato de la 006; avisa de desactualizado e inaccesible conservando la última lectura rotulada. | Cumple |
| IX. Evidencia | Pruebas de comportamiento + escenarios en navegador con esperado/observado en `docs/evidence/007/`. | Cumple |

Sin desviaciones constitucionales abiertas.

**Re-evaluación tras el diseño (Phase 1)**: sin cambios. Un punto queda vigilado: si el catálogo de
países de `paises.geojson` no cubre algún `country_id` presente en la base, se documenta como
cambio de la API (spec, Assumptions) en lugar de resolverlo en el cliente.

## Project Structure

### Documentation (this feature)

```text
specs/007-angular-dashboard/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── ui-contract.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
frontend/
├── public/
│   ├── config.json                # mode, apiUrl, refreshMs, skipNgrokWarning, staleAfterMs, requestTimeoutMs
│   └── datos/paises.geojson       # fronteras y catálogo de países (terremotos-demo.geojson se retira)
├── src/app/
│   ├── lib/                       # lógica pura, sin Angular ni Leaflet
│   │   ├── api-types.ts           # tipos del contrato de la 006
│   │   ├── adapt.ts               # validación y adaptación de respuestas
│   │   ├── filters.ts             # QueryFilters → parámetros; validación; UTC
│   │   ├── format.ts              # ND, fechas UTC, profundidad, magnitud
│   │   ├── status.ts              # derivación del estado (desactualizado, degradado, …)
│   │   └── *.test.ts              # pruebas de comportamiento (Vitest)
│   ├── data/
│   │   └── observatory.service.ts # lectura, ciclo de refresco, secuencia, última lectura
│   ├── map/ table/ charts/ status/ filters/   # componentes pequeños
│   └── app.component.*            # composición
├── netlify.toml  (raíz del repo, ya existe)
└── package.json                   # + vitest (dev, versión exacta), script "test"
docs/evidence/007/                 # esperado/observado y capturas
docs/report.md, README.md          # apartado y procedimiento de la defensa
```

**Structure Decision**: se mantiene `frontend/` como único proyecto. El componente único se divide
en componentes y un servicio, y toda lógica sin dependencias de Angular/Leaflet va a `lib/` para
probarla sin navegador. No se toca `api/` salvo necesidad demostrada.

## Orquestación (CLAUDE.md)

Sesión principal: modelo de estado y servicio de datos (`observatory.service`, `lib/status`), todo
lo que toca el sistema real (levantar el stack, navegador), evidencias, memoria e integración.
Sonnet en segundo plano: componentes de mapa, tabla y gráficos y sus pruebas de `lib/`. Haiku: README
y apartado del informe a partir de la evidencia. Cada tarea llevará etiqueta de agente y ficheros
permitidos; sin dos agentes sobre los mismos ficheros.

## Complexity Tracking

Sin violaciones que justificar.
