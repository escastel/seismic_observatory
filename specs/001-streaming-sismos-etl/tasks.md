---

description: "Task list for streaming seismic ETL and geospatial API"
---

# Tasks: Streaming de sismos con ETL y consulta geoespacial

**Input**: Design documents from `/specs/001-streaming-sismos-etl/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Organization**: Tasks are grouped by user story and, within each story, by service.
Database and Kafka are foundational prerequisites and must be operational before any
application service starts.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Crear la estructura inicial y configuración común sin implementar aún
las historias de usuario.

- [ ] T001 Crear la estructura raíz `producer/`, `consumer/`, `api/`, `db/init/`, `db/seeds/` y `tests/` según `specs/001-streaming-sismos-etl/plan.md`
- [ ] T002 [P] Crear `producer/requirements.txt`, `consumer/requirements.txt` y `api/requirements.txt` con las dependencias definidas en `specs/001-streaming-sismos-etl/plan.md`
- [ ] T003 [P] Crear configuración común por variables de entorno documentada en `producer/app/config.py`, `consumer/app/config.py` y `api/app/config.py`
- [ ] T004 [P] Crear el esqueleto de entrada `producer/app/main.py`, `consumer/app/main.py` y `api/app/main.py` con logging estructurado

---

## Phase 2: Foundational (Database and Kafka)

**Purpose**: Prerrequisitos bloqueantes para todas las historias.

**CRITICAL**: Database y Kafka deben estar saludables antes de iniciar Producer,
Consumer o API.

### Database

- [ ] T005 Crear `db/init/001_schema.sql` con `dim_geografia`, `dim_tiempo`, `fact_sismos` y `cuarentena` conforme a `specs/001-streaming-sismos-etl/data-model.md`
- [ ] T006 Añadir a `db/init/001_schema.sql` las restricciones: `external_id` único y no nulo, FK obligatorias, `country = 'Sin país asignado'` para eventos marítimos y `quality_dimension` limitada a Completitud, Validez, Exactitud, Consistencia, Oportunidad o Unicidad
- [ ] T007 Añadir a `db/init/001_schema.sql` los índices B-Tree sobre `dim_geografia.country`, `fact_sismos.event_time`, `fact_sismos.geografia_key`, `fact_sismos.magnitude` y `fact_sismos.external_id`
- [ ] T008 [P] Añadir datos mínimos reproducibles de calendario y catálogo geográfico en `db/init/002_seed_dimensions.sql`, sin reemplazar datos existentes al reiniciar PostgreSQL

### Kafka

- [ ] T009 Crear `compose.yaml` con el servicio `kafka` basado en `confluentinc/cp-kafka`, configuración KRaft local, healthcheck y topics `terremotos_raw` y `terremotos_replay`

### Docker

- [ ] T010 Añadir el servicio `postgres` basado en `postgres:15-postgis` a `compose.yaml`, volumen persistente, credenciales por variables de entorno y montaje de `db/init/`
- [ ] T011 Configurar en `compose.yaml` red interna, healthchecks y reintentos de conexión para que PostgreSQL y Kafka sean dependencias saludables, no solo dependencias de arranque
- [ ] T012 Verificar que `docker compose up --build -d` levanta únicamente los cinco servicios locales `postgres`, `kafka`, `producer`, `consumer` y `api` definidos por la constitución

**Checkpoint**: PostgreSQL y Kafka están disponibles, el esquema es repetible y los
topics existen; las historias pueden implementarse sin cambiar sus contratos base.

---

## Phase 3: User Story 1 - Ingestar y validar sismos (Priority: P1) — MVP

**Goal**: Ingerir features USGS, aplicar el WAF, enriquecerlos espacialmente y
persistirlos con at-least-once e idempotencia.

**Independent Test**: Publicar eventos válidos, inválidos, marítimos y repetidos;
verificar `fact_sismos`, `cuarentena`, clasificación geográfica y ausencia de
confirmación Kafka antes del commit PostgreSQL.

### Database

- [ ] T013 [US1] Implementar el upsert transaccional condicionado por `updated` en `consumer/app/persistence.py`: actualizar solo cuando `excluded.updated > fact_sismos.updated` y conservar una única fila por `external_id`
- [ ] T014 [US1] Implementar la inserción auditable en `cuarentena` en `consumer/app/persistence.py`, conservando payload, `source_topic`, partición, offset, dimensión de calidad y motivo concreto

### Producer

- [ ] T015 [P] [US1] Implementar la descarga del feed GeoJSON `earthquakes_feed.geojson` con `requests` y manejo explícito de feed inaccesible, vacío o malformado en `producer/app/feed.py`
- [ ] T016 [US1] Implementar el ciclo configurable de 60 segundos en `producer/app/main.py`, extrayendo cada `feature`, conservando atributos/geometría y publicando JSON con clave estable `id` en `terremotos_raw`
- [ ] T017 [US1] Implementar reintentos observables de conexión/publicación Kafka en `producer/app/main.py` sin descartar features silenciosamente

### Consumer

- [ ] T018 [P] [US1] Implementar validaciones WAF en `consumer/app/quality.py`: magnitud no nula y numérica, `longitude` en `[-180, 180]`, `latitude` en `[-90, 90]`, coordenadas finitas, e `id`/`updated` presentes
- [ ] T019 [P] [US1] Implementar el mapeo de fallos a las seis dimensiones de calidad en `consumer/app/quality.py`, usando Completitud para nulos, Validez para coordenadas erróneas y códigos estables para cada motivo
- [ ] T020 [P] [US1] Implementar carga única de `paises.geojson` y cruce Point in Polygon con GeoPandas/`shapely` en `consumer/app/spatial.py`, devolviendo país, continente y subregión
- [ ] T021 [US1] Garantizar en `consumer/app/spatial.py` que cualquier punto sin polígono terrestre recibe exactamente `Sin país asignado` y nunca el país más cercano
- [ ] T022 [US1] Implementar el consumidor de `terremotos_raw` con `enable_auto_commit=False` en `consumer/app/main.py`, separando parseo, WAF, enriquecimiento y persistencia
- [ ] T023 [US1] Coordinar en `consumer/app/main.py` la transacción PostgreSQL y Kafka: commit DB de upsert o cuarentena primero, `consumer.commit()` después, y offset sin confirmar ante cualquier fallo previo
- [ ] T024 [US1] Conservar `source_topic`, `kafka_partition`, `kafka_offset`, `external_id` y timestamps en los logs del pipeline de `consumer/app/main.py` para auditar reintentos y replay

### Docker

- [ ] T025 [US1] Crear `producer/Dockerfile` con `python:3.11-slim`, instalación de `producer/requirements.txt` y ejecución de `producer/app/main.py`
- [ ] T026 [US1] Crear `consumer/Dockerfile` con `python:3.11-slim`, dependencias GeoPandas/`shapely`, montaje de `paises.geojson` y ejecución de `consumer/app/main.py`
- [ ] T027 [US1] Añadir `producer` y `consumer` a `compose.yaml` con `depends_on` saludable para Kafka/PostgreSQL, variables de topics y volumen de datos espaciales

**Checkpoint**: La historia P1 funciona de extremo a extremo desde USGS hasta
PostgreSQL/cuarentena y puede demostrarse sin API.

---

## Phase 4: User Story 2 - Consultar eventos y estadísticas (Priority: P2)

**Goal**: Exponer eventos filtrables, estadísticas y GeoJSON para Angular/Leaflet
desde PostgreSQL.

**Independent Test**: Con datos conocidos en `fact_sismos`, comprobar filtros
combinables, respuestas vacías, errores de parámetros y las tres respuestas REST.

### API

- [ ] T028 [P] [US2] Crear modelos de consulta y respuesta en `api/app/schemas.py` para filtros ISO, magnitud, paginación, eventos, conteos y `FeatureCollection`
- [ ] T029 [P] [US2] Implementar pool `asyncpg` y manejo HTTP 503 en `api/app/db.py` con consultas parametrizadas y cierre limpio
- [ ] T030 [US2] Implementar `GET /api/eventos` en `api/app/main.py` y `api/app/queries.py` con filtros combinables `country`, `date_from`, `date_to`, `min_magnitude`, `max_magnitude`, `limit` y `offset`
- [ ] T031 [US2] Implementar la serialización GeoJSON `FeatureCollection` de `GET /api/eventos` en `api/app/main.py`, usando geometrías Point `[longitude, latitude, depth_km]` y propiedades geográficas
- [ ] T032 [US2] Implementar `GET /api/estadisticas/paises` en `api/app/main.py` y `api/app/queries.py` con filtros de fecha/magnitud y conteo de `Sin país asignado`
- [ ] T033 [US2] Implementar `GET /api/estadisticas/timeline` en `api/app/main.py` y `api/app/queries.py` con buckets `day`, `week` y `month`
- [ ] T034 [US2] Validar rangos y fechas incompatibles en `api/app/schemas.py`, devolviendo errores claros HTTP 400/422 y colecciones vacías válidas
- [ ] T035 [US2] Instalar middleware CORS en `api/app/main.py` con `CORS_ORIGINS`, wildcard para demo sin credenciales o lista explícita de Netlify/ngrok

### Docker

- [ ] T036 [US2] Crear `api/Dockerfile` con `python:3.11-slim`, instalación de `api/requirements.txt` y ejecución de `uvicorn api.app.main:app`
- [ ] T037 [US2] Añadir `api` a `compose.yaml` con dependencia saludable de PostgreSQL, puerto local documentado y variables `DATABASE_URL` y `CORS_ORIGINS`

### Frontend

- [ ] T038 [US2] Adaptar `frontend/src/app/app.component.ts` y `frontend/public/config.json` para consumir `/api/eventos` GeoJSON, conservar el header ngrok y mostrar país/continente/subregión cuando estén disponibles

**Checkpoint**: P1 y P2 funcionan conjuntamente; el frontend puede consultar el
backend remoto sin bloqueo CORS.

---

## Phase 5: User Story 3 - Reproducir histórico 2025 (Priority: P3)

**Goal**: Reproducir un histórico en un topic aislado a alta velocidad y verificar
trazabilidad, idempotencia y las mismas reglas del pipeline.

**Independent Test**: Publicar el histórico en `terremotos_replay` a una tasa al
menos diez veces superior al ciclo normal, y comparar publicados, persistidos,
cuarentena y duplicados.

### Producer

- [ ] T039 [P] [US3] Crear el publicador de replay en `producer/app/replay.py` que lea `db/seeds/historical_2025.jsonl`, publique cada evento en `terremotos_replay` y acepte una tasa configurable
- [ ] T040 [US3] Añadir validación de año 2025, contador de mensajes publicados y logging de lote/origen en `producer/app/replay.py`

### Consumer

- [ ] T041 [US3] Extender `consumer/app/main.py` para suscribirse a `terremotos_raw` y `terremotos_replay`, conservando `source_topic` sin mezclar silenciosamente ambos canales
- [ ] T042 [US3] Verificar que el replay usa exactamente `consumer/app/quality.py`, `consumer/app/spatial.py` y `consumer/app/persistence.py`, incluyendo cuarentena, `Sin país asignado` y upsert por `updated`

### Database

- [ ] T043 [US3] Preparar `db/seeds/historical_2025.jsonl` con un lote reproducible que incluya eventos válidos, inválidos, marítimos y repetidos para la demostración

### Docker

- [ ] T044 [US3] Montar `db/seeds/` y habilitar el comando de replay documentado en `compose.yaml` sin añadir un sexto servicio local

**Checkpoint**: El histórico puede procesarse de forma acelerada, trazable y
repetible sin alterar la ingesta normal.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Endurecimiento, documentación y validación transversal.

- [ ] T045 [P] Documentar variables, servicios, topics y troubleshooting en `README.md` enlazando `specs/001-streaming-sismos-etl/quickstart.md`
- [ ] T046 [P] Añadir logging de métricas de procesados, cuarentena, reintentos y lag en `producer/app/`, `consumer/app/` y `api/app/`
- [ ] T047 [P] Revisar `compose.yaml`, Dockerfiles y requirements para confirmar ausencia de Spark, Flink, Kubernetes, Streamlit y servicios Cloud
- [ ] T048 Ejecutar manualmente `docker compose up --build -d` y todos los escenarios de `specs/001-streaming-sismos-etl/quickstart.md`
- [ ] T049 Verificar manualmente el cumplimiento constitucional y documentar resultados de calidad según la regla 1-10-100, sin generar informe automático

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: sin dependencias; prepara rutas y configuración.
- **Phase 2 Foundational**: depende de Setup y bloquea todas las historias; primero
  PostgreSQL y Kafka, después los servicios de aplicación.
- **Phase 3 US1**: depende de Database/Kafka fundacionales; constituye el MVP.
- **Phase 4 US2**: depende de `fact_sismos` y del contrato de datos de US1.
- **Phase 5 US3**: depende del consumidor de US1 y de los topics fundacionales; puede
  ejecutarse después de US1 y en paralelo con parte de US2.
- **Phase 6 Polish**: depende de las historias objetivo completadas.

### User Story Dependencies

- **US1 (P1)**: depende únicamente de Phase 2.
- **US2 (P2)**: depende de la disponibilidad de `fact_sismos` creada por US1.
- **US3 (P3)**: depende del consumidor de US1 y puede probarse sin completar US2.

### Parallel Opportunities

- En Setup: T002-T004 pueden ejecutarse en paralelo después de T001.
- En Foundation: T005-T008 son tareas de Database; T009 es Kafka; T010-T012 integran
  Docker después de tener los contratos iniciales.
- En US1: T015, T018, T019 y T020 pueden ejecutarse en paralelo; T022-T024 esperan
  validación, espacial y persistencia.
- En US2: T028 y T029 pueden ejecutarse en paralelo; T030-T033 dependen de esos
  contratos y T035 es paralelo a las consultas.
- En US3: T039 y T043 pueden ejecutarse en paralelo; T041-T042 esperan T039 y US1.
- En Polish: T045-T047 son paralelizables; T048-T049 requieren el sistema completo.

## Parallel Example: User Story 1

```text
# Después de Phase 2:
T015 producer/app/feed.py
T018 consumer/app/quality.py
T019 consumer/app/quality.py
T020 consumer/app/spatial.py
T013-T014 consumer/app/persistence.py

# Luego integrar en orden:
T021 -> T022 -> T023 -> T024 -> T025-T027
```

## Parallel Example: User Story 2

```text
# Después de US1:
T028 api/app/schemas.py
T029 api/app/db.py
T035 api/app/main.py (CORS)

# Integrar contratos:
T030 -> T031
T032 y T033
T034 -> T036 -> T037 -> T038
```

## Implementation Strategy

1. **MVP**: completar Phase 1, Phase 2 y US1; demostrar ingesta, WAF,
   enriquecimiento, cuarentena e idempotencia.
2. **Incremento de consulta**: completar US2 y conectar Angular mediante CORS/ngrok.
3. **Incremento de demostración**: completar US3 con replay aislado de 2025.
4. **Cierre**: ejecutar quickstart, revisión constitucional y documentación manual
   de calidad.

### Task Format Validation

Todas las tareas usan checkbox `- [ ]`, identificador secuencial `T###`, marcador
`[P]` solo cuando son paralelizables, etiqueta `[US#]` en fases de historia y una
ruta de archivo concreta. Las tareas fundacionales y de polish no llevan etiqueta de
historia, conforme al formato requerido.
