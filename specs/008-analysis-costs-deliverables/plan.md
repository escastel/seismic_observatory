# Implementation Plan: Análisis, rendimiento, costes y cierre de entregables

**Branch**: `008-analysis-costs-deliverables` | **Date**: 2026-11-17 | **Spec**: `spec.md`

**Input**: Feature specification from `/specs/008-analysis-costs-deliverables/spec.md`

## Summary

Feature casi enteramente documental y de evidencia: produce en `docs/report.md` el apartado de
análisis (≥ 3 conclusiones con consultas regenerables), el de complejidad y rendimiento (tres
operaciones, tres tamaños, 100 M razonado), el de costes (medidas frente a supuestos, límites de
las cuotas gratuitas, revisión de la evaluación financiera) y las matrices de trazabilidad §11,
§12 y §13, más un guion de apoyo. Las cifras salen de la API (006) o de SQL sobre
`core.event_current`; el código nuevo se limita a un script de medición mínimo (búsqueda
secuencial frente a diccionario frente a consulta con y sin índice, con tiempo y memoria) y a la
ampliación de la latencia de la API con 1.000.000 de filas en el esquema sintético `bench`.
No se toca el contrato de la 006 ni el panel de la 007.

## Technical Context

**Language/Version**: Python 3.11 (contenedor `tests`, ya existente); SQL de PostgreSQL 16.4; Markdown.

**Primary Dependencies**: ninguna nueva. Se reutilizan `tests/benchmark/index_benchmark.py` y
`tests/benchmark/api_latency.py`; memoria con `tracemalloc` y `resource` de la biblioteca estándar.

**Storage**: PostgreSQL existente. Esquema `bench` efímero y sintético para la escala; sin tablas
nuevas en `core` ni `replay`.

**Testing**: pytest en el contenedor `tests`. Pruebas de comportamiento del script de medición
(entrada pequeña, salidas coherentes, el esquema `bench` no queda detrás). Nunca dos ejecuciones
de `tests/db` a la vez (CLAUDE.md).

**Target Platform**: Windows 11 + Docker Desktop (medido) y Linux (hueco para la persona autora).

**Project Type**: documentación + scripts de medición (sin servicio nuevo).

**Performance Goals**: las de la 006 (mediana ≤ 2.000 ms); esta feature mide, no impone nuevos objetivos.

**Constraints**: datos sintéticos fuera del análisis real; esquema `bench` eliminado al terminar;
sin `.env` ni `docker compose config`; documentación en español, código en inglés.

**Scale/Scope**: 3 tamaños (10.000, 100.000, 1.000.000) para estructuras y consultas; API con
1.000.000 de filas sintéticas; análisis real con ~34.000 eventos actuales (crece con el feed).

## Constitution Check

| Principio | Estado |
|---|---|
| I Arquitectura local | Sin servicios nuevos. OK |
| II Idempotencia | No se toca. OK |
| III Calidad | Las conclusiones declaran registros sin valor (ND). OK |
| IV Integración espacial | «Sin país asignado» entra en el análisis. OK |
| V Procedencia | Cada cifra lleva consulta e instante. OK |
| VI Aislamiento | Reproducción y sintéticos fuera del análisis real; reproducción, si se usa, aparte. OK |
| VII Analítica y comparación | Mismos filtros, días con cero en el denominador, ND con media cero, aviso de periodo incompleto, sin predicción. Pilar de la feature. OK |
| VIII Contrato | Sin cambios. OK |
| IX Evidencia y costes | Tres tamaños, equipo y procedimiento; medida frente a supuesto; sin beneficios inventados. Pilar de la feature. OK |

Sin desviaciones. Tras el diseño se reevalúa: igual resultado.

## Project Structure

### Documentation (this feature)

```text
specs/008-analysis-costs-deliverables/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── report-sections.md   # estructura exigida de cada apartado y entrada de la memoria
└── tasks.md                 # /speckit-tasks
```

### Source Code (repository root)

```text
tests/benchmark/
├── api_latency.py            # se amplía: --schema bench / 1.000.000 filas (sin duplicar lo medido)
├── structure_benchmark.py    # nuevo: secuencial vs diccionario vs consulta, tiempo y memoria
└── (index_benchmark.py)      # se reutiliza por referencia, no se modifica
tests/analysis/               # consultas reproducibles de las conclusiones (SQL/llamadas a la API)
docs/
├── report.md                 # + análisis, complejidad, costes, matrices, índice coherente
├── evaluacion-financiera.md  # revisado: flujos con supuestos trazables o retirados
├── guion-explicacion.md      # guion de apoyo (nuevo)
└── evidence/008/             # esperado/observado, salidas y capturas
```

**Structure Decision**: sin código de producto nuevo; los scripts viven con los benchmarks
existentes y las consultas del análisis junto a `tests/analysis`. Todo el texto en `docs/`.

## Complexity Tracking

Sin violaciones que justificar.
