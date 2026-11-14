# Implementation Plan: Plataforma y modelo de datos del observatorio

**Branch**: `002-platform-data-model` | **Date**: 2026-11-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-platform-data-model/spec.md`

## Summary

Rehacer la base sobre la que se apoyan las demás funcionalidades: un `compose.yaml` endurecido
con los cinco servicios obligatorios, salud y reintentos reales, y un modelo de datos nuevo en
PostgreSQL con tres esquemas (`core`, `replay`, `bench`), una única definición parametrizada de
las tablas de eventos y una función `apply_event_version` que concentra la regla de versiones.
El diseño del modelo se ha validado en un PostgreSQL desechable con el catálogo real: la
secuencia de la FAQ 12 da 2 eventos actuales y 3 versiones, y el mismo identificador convive en
`core` y `replay` sin interferir (ver [research.md](research.md)).

Los servicios actuales se adaptan lo mínimo para seguir moviendo un evento de extremo a extremo
sobre el modelo nuevo; su comportamiento se rehace en las specs 003 (ingesta), 004 (consumidor y
calidad) y 006 (API).

## Technical Context

**Language/Version**: Python 3.11 (imagen `python:3.11.10-slim-bookworm`); SQL de PostgreSQL 16

**Primary Dependencies**: aiokafka 0.12.0, asyncpg 0.30.0, FastAPI 0.115.6, uvicorn 0.34.0,
pydantic 2.10.4, GeoPandas 1.0.1 y Shapely 2.0.6 (solo consumidor), requests 2.32.3 (productor)

**Storage**: PostgreSQL 16.4 (esquemas `core`, `replay`, `bench`); Kafka 3.7 en modo KRaft
(`confluentinc/cp-kafka:7.7.1`); ficheros de datos en `data/`, fuera de Git

**Testing**: pytest en contenedor (`compose.dev.yaml`) contra una base temporal
`observatory_test`; medición con `EXPLAIN (ANALYZE, BUFFERS)`

**Target Platform**: Docker Engine 26+ con Compose v2 en el equipo del alumno (Linux; válido en
Windows y macOS con Docker Desktop)

**Project Type**: sistema de datos con varios servicios (pipeline en streaming, API y SPA)

**Performance Goals**: cinco servicios sanos en menos de 3 minutos; consultas de la API por
intervalo, país y magnitud mínima resueltas con índice en la tabla de 1.000.000 de filas
sintéticas

**Constraints**: equipo de referencia con 12 hilos y 8 GB de RAM; solo la API publicada, en
`127.0.0.1`; sin PostGIS, Spark, Flink ni Kubernetes; dependencias fijadas; código en inglés y
documentación en español

**Scale/Scope**: unos 16.000 eventos por año con magnitud ≥ 4 en el histórico obligatorio; unos
200 eventos nuevos y hasta 10.080 extracciones por semana en el feed; mediciones hasta 1.000.000
de filas; el modelo no debe impedir cargar el catálogo completo desde 1900

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación previa | Evaluación tras el diseño |
|---|---|---|
| I. Arquitectura reproducible y superficie mínima | Cumple: cinco servicios, salud, reintentos, volúmenes, retención, sin puertos de Kafka ni PostgreSQL | Cumple ([contracts/runtime.md](contracts/runtime.md)) |
| II. Al menos una vez, idempotente y versionada | Cumple en el modelo: claves únicas y escritura condicionada | Cumple: `apply_event_version` verificada; las garantías de offset (empezar por el principio, no avanzar tras un fallo) se corrigen en esta funcionalidad (R20) |
| III. Calidad: conservar, señalar o cuarentena | Cumple en el modelo: magnitud y profundidad anulables, sin mínimos, `quality_flags`, cuarentena con original | Cumple en el modelo. Desviación temporal: las reglas del consumidor no cambian hasta la spec 004 |
| IV. Integración espacial | Cumple: `dim_country` con clave `ADM0_A3`, país anulable | Cumple: 177 entidades, 5 sin ISO |
| V. Original y procedencia | Cumple: `extraction`, `raw_payload` con huella y retención, `payload` en cada versión | Cumple; retención ajustada a 7 días por estimación de volumen |
| VI. Aislamiento de la reproducción | Cumple: esquema `replay` propio, misma plantilla | Cumple, verificado |
| VII. Analítica desde el estado actual | Cumple: no hay tablas de contadores; `dim_date` aporta los días sin eventos | Cumple: `message_log` es auditoría de ingesta, no fuente de recuentos (R19) |
| VIII. Contrato de la API | Fuera de alcance salvo `last_ingestion`, que el modelo soporta | Cumple en lo que afecta al modelo |
| IX. Evidencia ejecutada | Cumple: pruebas de comportamiento, medición con tres tamaños | Cumple ([quickstart.md](quickstart.md)) |
| Idioma y repositorio público | Cumple: identificadores en inglés, documentos en español, datos fuera de Git | Cumple |

Sin violaciones en lo que esta funcionalidad construye. Dos elementos añaden complejidad y se
justifican en *Complexity Tracking*.

**Desviaciones temporales conocidas**: al terminar la 002 siguen sin cumplirse tres principios
en el comportamiento heredado de los servicios. Ninguna la introduce esta funcionalidad y el
modelo ya da soporte a las tres. Mientras existan, la rama no se fusiona en `main`.

| Principio | Qué sigue sin cumplirse | La cierra |
|---|---|---|
| III | El consumidor envía la magnitud nula a cuarentena y rechaza la negativa | spec 004 |
| V | El productor no registra las extracciones ni guarda el original, y no purga `raw_payload` | spec 003 |
| VIII | La API devuelve un formato propio por defecto, tiempos en ISO y un `last_ingestion` que no es la última consulta correcta a USGS | spec 006 |

## Project Structure

### Documentation (this feature)

```text
specs/002-platform-data-model/
├── plan.md              # Este fichero
├── research.md          # Decisiones técnicas y verificaciones
├── data-model.md        # Modelo conceptual, lógico y físico
├── quickstart.md        # Escenarios de validación
├── contracts/
│   ├── database.md      # Interfaz del modelo para los servicios
│   └── runtime.md       # Servicios, red, topics, variables y salud
├── checklists/
│   └── requirements.md
└── tasks.md             # Lo genera /speckit-tasks
```

### Source Code (repository root)

```text
compose.yaml                     # REHACER: cinco servicios + perfil tunnel
compose.dev.yaml                 # NUEVO: servicio tests para pruebas y mediciones
.env.example                     # REHACER según contracts/runtime.md
.dockerignore                    # AMPLIAR: data/, resources/, docs/

db/
├── init/
│   └── 00-init.sh               # NUEVO: punto de entrada; llama a sql/apply.sh
├── sql/                         # NUEVO: fuente única del modelo
│   ├── apply.sh                 # aplica los ficheros en orden a la base indicada
│   ├── 010_roles_schemas.sql
│   ├── 020_dimensions.sql       # dim_country desde el GeoJSON, dim_date
│   ├── 030_extraction.sql       # extraction, raw_payload, purge_raw_payload
│   ├── 040_event_tables.sql     # PLANTILLA por esquema + apply_event_version
│   ├── 050_schema_rules.sql     # reglas de replayed_at y replay.reset()
│   ├── 060_indexes.sql          # PLANTILLA: índices que superen la medición
│   └── 070_grants.sql
└── seeds/                       # se mantiene; README actualizado; contenido en 003 y 005

common/                          # NUEVO: código compartido por los tres servicios
├── settings.py                  # lectura y validación de variables
├── logging.py
├── retry.py                     # espera exponencial con tope
├── db.py                        # pool asyncpg con search_path
├── topics.py                    # creación idempotente de topics
└── health.py                    # latido y comprobación

producer/
├── Dockerfile                   # REHACER: imagen fijada, usuario sin privilegios, sin datos
├── requirements.in / .txt       # NUEVO / REGENERAR con transitivas fijadas
└── app/                         # ADAPTAR persistence.py y main.py al modelo nuevo
consumer/
├── Dockerfile, requirements.*   # ídem
└── app/                         # ADAPTAR persistence.py y main.py; quitar ensure_schema
api/
├── Dockerfile, requirements.*   # ídem; eliminar ngrok, geoalchemy2, pydantic-settings
└── app/                         # ADAPTAR queries.py, db.py; quitar ngrok de main.py

tests/
├── Dockerfile                   # NUEVO: imagen de pruebas con cliente psql
├── db/                          # NUEVO: secuencia FAQ 12, nulos, rangos, aislamiento, roles
├── benchmark/
│   └── index_benchmark.py       # NUEVO: medición sin/con índice en tres tamaños
├── startup/
│   └── cold_start.sh            # NUEVO: diez arranques desde cero cronometrados
├── integration/                 # benchmark_scaling.py y load_test.py se conservan para la 008
├── unit/                        # se conservan las que prueban comportamiento; nuevas de common/
└── contract/, test_enunciado_compliance.py   # ELIMINAR las que buscan texto en el código

docs/
├── report.md                    # NUEVO: memoria; aquí, diccionario de datos y modelo
└── evidence/002/                # NUEVO: resultados de quickstart.md

README.md                        # REHACER los apartados de arranque, parada y recreación
```

**Ficheros que se eliminan**: `db/init/001_schema.sql` a `006_mag_type.sql`;
`tests/contract/test_enunciado_api_contract.py`, `tests/contract/test_frontend_contract.py` y
`tests/test_enunciado_compliance.py`.

**Structure Decision**: se conserva la estructura de un directorio por servicio que ya tiene el
repositorio y se añaden `common/` para el código compartido, `db/sql/` como fuente única del
modelo y `compose.dev.yaml` para pruebas. No se introduce un directorio `src/` ni se fusionan
las imágenes: solo el consumidor necesita las bibliotecas geoespaciales.

## Orden de implementación

1. **Modelo**: configuración local, recreación del volumen (con confirmación), `db/sql/` y
   `db/init/00-init.sh`; pruebas de `tests/db` en rojo y después en verde (V3 a V7 de
   [quickstart.md](quickstart.md)).
2. **Plataforma**: `compose.yaml`, Dockerfiles, dependencias fijadas, `common/`
   (V1, V2, V9, V10).
3. **Continuidad**: adaptación mínima de productor, consumidor y API al modelo nuevo; un evento
   real llega de USGS al mapa (V8).
4. **Optimización**: medición de índices y decisión de cuáles permanecen (V11).
5. **Documentación y evidencias**: diccionario y modelo en `docs/report.md`, README y
   `docs/evidence/002/` (V12).

## Riesgos

| Riesgo | Mitigación |
|---|---|
| El volumen local guarda el modelo anterior y la inicialización no se vuelve a ejecutar | Procedimiento explícito de recreación en README y quickstart; la base actual solo tiene datos de prueba |
| La adaptación mínima de los servicios crece hasta invadir las specs 003, 004 y 006 | Límite: solo cambian las capas de persistencia, el arranque y las dos garantías de offset de R20; ninguna regla de validación ni endpoint nuevo |
| `postgres:16.4` no arranca sobre el volumen actual de PostgreSQL 15 | La recreación del volumen es una tarea explícita de la fase 2, antes de la primera prueba, y pide confirmación |
| Sin puertos publicados, las pruebas desde el equipo dejan de funcionar | `compose.dev.yaml` ejecuta las pruebas dentro de la red |
| La sintaxis del agente de ngrok cambia entre versiones | Imagen fijada y comprobación V10 antes de documentar la orden |
| El panel publicado en Netlify deja de recibir datos mientras dura el rehacer | El trabajo va en ramas; `main` solo se actualiza cuando la API vuelve a cumplir el contrato |

## Complexity Tracking

| Elemento | Por qué se necesita | Alternativa más simple descartada porque |
|---|---|---|
| Tres roles de base de datos | La API es lo único expuesto a Internet; con solo lectura, un fallo suyo no puede alterar datos | Un único usuario deja el almacén a merced de cualquier error de la capa pública |
| Función `apply_event_version` en la base | La regla de versiones queda junto a sus restricciones, se prueba con SQL y devuelve el resultado que la memoria necesita contar | Dos sentencias desde Python dan la misma garantía, pero la regla no se puede probar sin el consumidor y habría que duplicarla para cada esquema |
