# Implementation Plan: Consumidor y calidad de los datos

**Branch**: `004-consumer-quality` | **Date**: 2026-11-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-consumer-quality/spec.md`

## Summary

Rehacer las reglas del consumidor para cumplir el principio III: un catálogo de reglas con códigos
estables donde solo va a cuarentena lo intratable, lo ausente se conserva nulo, las anomalías se
señalan con marcas y las reglas heredadas que contradecían la constitución se retiran. Se añaden
la asignación de país determinista con comprobación de unicidad, una orden de reprocesado
idempotente de la cuarentena, un conjunto de casos sintéticos identificados, las consultas de
recuento y el apartado de calidad de la memoria con las seis dimensiones.

El modelo de las specs 002 y 003 solo cambia en tres puntos aditivos y justificados (R9 de
[research.md](research.md)): columnas de reprocesado en la cuarentena, `attempt` en el registro de
mensajes y el resultado `excluded`. No se toca el productor, la API ni el panel.

## Technical Context

**Language/Version**: Python 3.11 (imagen `python:3.11.10-slim-bookworm`); SQL de PostgreSQL 16

**Primary Dependencies**: las ya fijadas: aiokafka 0.12.0, asyncpg 0.30.0, GeoPandas 1.0.1,
Shapely 2.0.6. Sin dependencias nuevas

**Storage**: PostgreSQL 16.4, esquemas `core` y `replay`; plantilla idempotente
`db/sql/041_consumer_quality.sql`

**Testing**: pytest en el contenedor `tests` contra `observatory_test`; casos sintéticos con el
sistema real

**Target Platform**: Docker Engine 26+ con Compose v2; Windows 11 (Git Bash) y Linux

**Project Type**: sistema de datos con varios servicios

**Performance Goals**: el consumidor mantiene el ritmo actual (unos 700 mensajes/s con la base
local); un mensaje defectuoso no retrasa al siguiente más de 1 s

**Constraints**: sin cambios en productor, API y panel; modelo solo con los tres cambios
justificados; cinco servicios en el arranque normal; código en inglés y documentación en español

**Scale/Scope**: unos 33.000 eventos actuales, 2 filas reales de cuarentena, 25 casos sintéticos
previstos, 177 polígonos

## Constitution Check

| Principio | Evaluación previa | Evaluación tras el diseño |
|---|---|---|
| I. Arquitectura reproducible | Cumple: sin servicios nuevos en el arranque | Cumple: `quality-reprocess` solo bajo el perfil `tools`; sin puertos ni dependencias |
| II. Al menos una vez, idempotente | Cumple: transacción por mensaje y offset tras el commit se mantienen | Cumple: el reprocesado es idempotente; `attempt` permite reprocesar sin duplicar |
| III. Calidad | **Es el objetivo y cierra la desviación abierta** | Cumple: nulos conservados, negativos no rechazados, cuarentena con todos los motivos y el original, exclusiones con motivo, nada se pierde ni bloquea la cola |
| IV. Integración espacial | Parcial: orden de polígonos decide en fronteras | Cumple: unicidad comprobada, regla determinista documentada, país nulo para el mar |
| V. Original y procedencia | No afectado | Cumple: el original sigue íntegro en `event_version.payload` y en la cuarentena |
| VI. Aislamiento de la reproducción | Cumple | Cumple: mismas reglas en los tres topics, cada uno a su esquema; el reprocesado respeta el esquema de cada fila |
| VII. Analítica desde el estado actual | Cumple: sin contadores | Cumple: recuentos solo por SQL sobre lo almacenado, con denominador y sin sintéticos |
| VIII. Contrato de la API | Fuera de alcance | Sin cambios; la magnitud nula llega nula y contada para la 006 |
| IX. Evidencia ejecutada | Cumple | Cumple: casos sintéticos con el sistema real y evidencia en `docs/evidence/004/` |
| Idioma y repositorio público | Cumple | Cumple: códigos y marcas en inglés, documentación en español; sin datos en Git |

Sin violaciones; no hay entradas en *Complexity Tracking*. **Desviación que se cierra**: principio
III (magnitud nula). Siguen abiertas la del principio VIII (spec 006) y, en el panel, la
presentación de ND (spec 007).

## Project Structure

### Documentation (this feature)

```text
specs/004-consumer-quality/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── rules-catalog.md     # Cada regla, su código y su justificación
│   └── reprocess.md         # Órdenes de reprocesado e inyección de sintéticos
├── checklists/requirements.md
└── tasks.md                 # Lo genera /speckit-tasks
```

### Source Code (repository root)

```text
db/
├── sql/041_consumer_quality.sql   # NUEVO: plantilla idempotente (columnas, clave, CHECK)
├── sql/apply.sh                   # AMPLIAR: 041 como plantilla; opción de aplicar un solo fichero
└── queries/quality.sql            # NUEVO: recuentos con nombre

consumer/app/
├── rules.py                       # NUEVO: catálogo y evaluación (sustituye a quality.py)
├── quality.py                     # ELIMINAR
├── spatial.py                     # REHACER: todas las coincidencias, orden, ambigüedad, unicidad
├── persistence.py                 # ADAPTAR: marcas, excluded, attempt, ON CONFLICT con attempt
├── main.py                        # ADAPTAR: usar rules.py, sintéticos, comprobación del catálogo
└── reprocess.py                   # NUEVO: orden de reprocesado

common/settings.py                   # SIN CAMBIOS (el reprocesado usa consumer())

compose.yaml                         # AÑADIR quality-reprocess (perfil tools); montar db/queries
tests/
├── synthetic/{__init__,cases,inject}.py   # NUEVO
├── unit/test_rules.py, test_rules_catalog.py, test_spatial.py (REHACER)
├── unit/test_quality.py            # ELIMINAR (prueba quality.py)
├── db/test_consumer_rules.py, test_reprocess.py, test_message_counts.py, test_quality_queries.py  # NUEVOS
├── db/helpers.py, test_consumer_persistence.py, test_provenance.py  # ADAPTAR a attempt y a reglas nuevas
docs/report.md                       # AMPLIAR: calidad de los datos; diccionario
docs/evidence/004/                   # NUEVO
README.md                            # AMPLIAR: reprocesado y sintéticos
specs/002-platform-data-model/contracts/database.md  # ACTUALIZAR (attempt, excluded)
```

**No se toca**: `producer/`, `api/`, `frontend/`, `common/` (salvo lo indicado).

**Structure Decision**: se mantiene un directorio por servicio. El reprocesado vive en el paquete
del consumidor porque reutiliza sus reglas y su escritura; así no hay dos implementaciones.

## Orden de implementación

1. **Modelo y reglas puras**: `041`, `rules.py`, catálogo y pruebas unitarias (sin Docker salvo la
   plantilla).
2. **País**: `spatial.py` y sus pruebas (independiente del anterior; puede ir en paralelo).
3. **Consumidor**: persistencia y `main.py` con las reglas nuevas, y sus pruebas de base.
4. **Reprocesado y sintéticos**: `reprocess.py`, `cases.py`, `inject.py`.
5. **Recuentos**: `quality.sql` y pruebas.
6. **Sistema real**: aplicar `041`, inyectar, reprocesar, reiniciar (V1–V7).
7. **Memoria y evidencias**: calidad en seis dimensiones (V8–V9).

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Cambiar la clave de `message_log` rompe sentencias existentes | Se actualizan todas (`persistence.py`, ayudantes y pruebas) y las 303 pruebas previas siguen en verde (V9) |
| Aplicar `041` al volumen existente | Plantilla idempotente, probada dos veces seguidas y sobre una base con datos |
| Las reglas nuevas aceptan más eventos y algo choca con el modelo | `model_constraint_violation` a cuarentena; el consumidor no se bloquea |
| La asignación determinista cambia países ya guardados | Solo cambia en fronteras con varias coincidencias; se cuenta antes y después y se documenta |
| El reprocesado compite con el consumidor en marcha | Misma transacción y misma regla de versiones; la idempotencia de `apply_event_version` lo absorbe |
| Pruebas de base de datos en paralelo | Se ejecutan en serie; la base temporal es compartida |

## Complexity Tracking

Sin violaciones de la constitución que justificar.
