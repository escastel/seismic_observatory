# Implementation Plan: API de consulta conforme al contrato

**Branch**: `006-query-api` | **Date**: 2026-11-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-query-api/spec.md`

## Summary

La API heredada (FastAPI + asyncpg, `api/app/`) se ajusta al contrato `CONTRATO-API.md` sin
reescribirla desde cero: se conservan el arranque con reintentos, el pool de solo lectura y el
filtro compartido por todas las consultas; se sustituyen la forma de la respuesta, el cálculo de
`last_ingestion`, la agregación (ventanas de una hora UTC) y el tratamiento de errores.

Las decisiones de diseño (detalle en [research.md](research.md)):

- `GET /api/eventos` devuelve siempre un `FeatureCollection` con `metadata`; el máximo de puntos es
  1.000 (configurable), con `limit`/`offset` y `next_offset`.
- `mode=live|replay` elige **el pool**, no el texto de la consulta: el pool real usa
  `search_path = core` y el de reproducción `replay, core` (mismo patrón que el consumidor, spec
  005). Una respuesta no puede mezclar esquemas porque cada petición usa un único pool.
- `last_ingestion` sale de `core.extraction` (último `requested_at` de una consulta al feed con
  resultado `ok` o `not_modified`), con el índice parcial que ya existe.
- Las estadísticas se calculan en SQL sobre el conjunto completo que cumple el filtro (nunca sobre
  una página) con el **mismo constructor de filtros** que el mapa, y dentro de una transacción de
  solo lectura con instantánea única.
- Un fallo de la base es siempre un 503 con cuerpo JSON; un parámetro inválido es siempre un 422.
- Se retiran todos los alias y rutas heredados; el frontend entregado usa dos (`country`,
  `format`) y la adaptación del panel es de la spec 007 (R8).

Sin cambios en el modelo ni en los índices de las specs 002 a 005 (R9). Sin dependencias nuevas.

## Technical Context

**Language/Version**: Python 3.11 (imagen de la API)

**Primary Dependencies**: las ya fijadas (FastAPI, asyncpg, pydantic, uvicorn). Sin dependencias
nuevas

**Storage**: PostgreSQL 16.4, esquemas `core` y `replay`, rol `observatory_reader` (solo
`SELECT`, ya concedido sobre ambos esquemas en `070_grants.sql`)

**Testing**: pytest en el contenedor `tests`; pruebas unitarias de lo puro (constructor de
filtros, serialización, comparación) y pruebas de comportamiento con la API real contra la base
`observatory_test`; verificación final con el sistema real mediante la skill `verify-stack`

**Target Platform**: Docker Engine 26+ con Compose v2; Windows 11 (Git Bash) y Linux

**Project Type**: servicio web (API de solo lectura)

**Performance Goals**: página de 1.000 eventos y estadísticas de un día, un mes y un año de datos
de 2025 en menos de 2 s (SC-008); se mide en tres tamaños de resultado

**Constraints**: solo lectura; sin consultar USGS; sin rutas de escritura ni de administración;
sin cookies; puerto solo en `127.0.0.1`; código en inglés y documentación en español; LF y
`python3` en `.specify/`

**Scale/Scope**: catálogo 2025 con magnitud ≥ 4 (unos 17.000 eventos), hasta 1.000.000 de filas
sintéticas en las pruebas de escala de la spec 002; tres endpoints

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación | Estado |
|---|---|---|
| I. Superficie mínima | Un servicio, puerto solo en `127.0.0.1`, sin rutas de escritura ni administración; Swagger UI desactivada (R7). | Cumple |
| II. Idempotencia | La API solo lee `event_current`; una sola versión por evento por construcción (clave primaria). | Cumple |
| III. Calidad | Nulos como `null`, magnitud nula no cumple `min_mag` y se cuenta aparte; cuarentena visible en `metadata`; nada se rellena con ceros. | Cumple |
| IV. Espacial | Se muestra `country_id`/`country_name` tal cual; país nulo = «Sin país asignado», dentro del análisis. | Cumple |
| V. Original y procedencia | `last_ingestion` sale de `core.extraction` (consulta registrada), no de filas. | Cumple |
| VI. Aislamiento | Un pool por modo, `replayed_at` y etiqueta «REPRODUCCIÓN» en toda respuesta de reproducción; filtro defensivo de sintéticos en modo real. | Cumple |
| VII. Analítica derivada | Todo en SQL sobre el estado actual; ventanas de una hora UTC con extremo excluido; denominador con días vacíos; ND; aviso de periodo incompleto. | Cumple |
| VIII. Contrato | Esta spec lo cierra; CORS sin credenciales, errores explícitos. | Cumple |
| IX. Evidencia | `docs/evidence/006/` con esperado/observado, EXPLAIN y latencia en tres tamaños. | Cumple |

Sin desviaciones constitucionales abiertas.

**Re-evaluación tras el diseño (Phase 1)**: sin cambios; el diseño no añade tablas, índices ni
servicios. Dos decisiones de interpretación quedan documentadas como desviaciones del texto
literal del encargo y se llevarán a la memoria: `not_modified` cuenta como consulta correcta
(R3) y las estadísticas ante truncado se calculan sobre el total real, no se rechazan (R6).

## Project Structure

### Documentation (this feature)

```text
specs/006-query-api/
├── plan.md
├── research.md
├── data-model.md        # qué lee la API y cómo se proyecta (sin tablas nuevas)
├── quickstart.md        # escenarios V1–V12 de verificación
├── contracts/
│   └── api.md           # contrato HTTP implementado (parámetros, metadata, errores)
├── checklists/requirements.md
└── tasks.md             # lo genera /speckit-tasks
```

### Source Code (repository root)

```text
api/app/
├── main.py              # rutas, CORS, manejadores de error; delgado
├── db.py                # dos pools (live: core; replay: replay, core) con reintento
├── filters.py           # parámetros de consulta validados + constructor único de WHERE   (nuevo)
├── queries.py           # SQL: página, total, nulos, cuarentena, última ingesta, agregaciones
├── serialize.py         # milisegundos Unix, finitud, Feature/FeatureCollection, metadata    (nuevo)
├── stats.py             # ventanas, distribuciones, comparación histórica                   (nuevo)
└── schemas.py           # solo modelos de respuesta que sigan haciendo falta
common/settings.py       # ApiSettings: API_MAX_FEATURES (opcional, 1000)
compose.yaml             # api: pasa API_MAX_FEATURES con valor por defecto
tests/
├── unit/                # filtros, serialización, comparación, orden de ventanas (puro)
├── contract/test_api_contract.py   # reescrito: rutas, CORS, 422, 503, forma de la respuesta
├── api/                 # comportamiento con la base real (casos de la historia 8)        (nuevo)
└── benchmark/api_latency.py        # latencia en tres tamaños y EXPLAIN                  (nuevo)
docs/evidence/006/       # esperado/observado
```

**Structure Decision**: se mantiene la estructura de la API heredada y se reparte `main.py` en
módulos pequeños para que el constructor de filtros sea uno solo (garantía de que mapa y
estadísticas filtran igual, principio VII) y lo puro se pruebe sin base.

## Orquestación (CLAUDE.md)

- Sesión principal: modelo de respuesta y contrato (`contracts/api.md`), `filters.py`,
  `queries.py`, fases con el sistema real (Docker, base), evidencias, memoria e integración.
- Sonnet en segundo plano: `serialize.py`, `stats.py`, pruebas unitarias y de comportamiento,
  `api_latency.py` y reescritura de `test_api_contract.py`.
- Haiku: README (ejemplos de consulta) y tablas del apartado de la memoria.
- Dos agentes a la vez solo con ficheros disjuntos; `tests/db` y `tests/query_api` comparten
  `observatory_test`, así que nunca se ejecutan a la vez y la suite completa la lanza solo la
  sesión principal.

## Complexity Tracking

Sin violaciones que justificar.
