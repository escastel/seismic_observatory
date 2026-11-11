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

- [X] T001 Crear la estructura raíz `producer/`, `consumer/`, `api/`, `db/init/`, `db/seeds/` y `tests/` según `specs/001-streaming-sismos-etl/plan.md`
- [X] T002 [P] Crear `producer/requirements.txt`, `consumer/requirements.txt` y `api/requirements.txt` con las dependencias definidas en `specs/001-streaming-sismos-etl/plan.md`
- [X] T003 [P] Crear configuración común por variables de entorno documentada en `producer/app/config.py`, `consumer/app/config.py` y `api/app/config.py`
- [X] T004 [P] Crear el esqueleto de entrada `producer/app/main.py`, `consumer/app/main.py` y `api/app/main.py` con logging estructurado

---

## Phase 2: Foundational (Database and Kafka)

**Purpose**: Prerrequisitos bloqueantes para todas las historias.

**CRITICAL**: Database y Kafka deben estar saludables antes de iniciar Producer,
Consumer o API.

### Database

- [X] T005 Crear `db/init/001_schema.sql` con `dim_geografia`, `dim_tiempo`, `fact_sismos` y `cuarentena` conforme a `specs/001-streaming-sismos-etl/data-model.md`
- [X] T006 Añadir a `db/init/001_schema.sql` las restricciones: `external_id` único y no nulo, FK obligatorias, `country = 'Sin país asignado'` para eventos marítimos y `quality_dimension` limitada a las 7 dimensiones: Completitud, Validez, Exactitud, Consistencia, Oportunidad, Unicidad o Frescura
- [X] T007 Añadir a `db/init/001_schema.sql` los índices B-Tree sobre `dim_geografia.country`, `fact_sismos.event_time`, `fact_sismos.geografia_key`, `fact_sismos.magnitude` y `fact_sismos.external_id`
- [X] T008 [P] Añadir datos mínimos reproducibles de calendario y catálogo geográfico en `db/init/002_seed_dimensions.sql`, sin reemplazar datos existentes al reiniciar PostgreSQL

### Kafka

- [X] T009 Crear `compose.yaml` con el servicio `kafka` basado en `confluentinc/cp-kafka`, configuración KRaft local, healthcheck y topics `terremotos_raw` y `terremotos_replay`

### Docker

- [X] T010 Añadir el servicio `postgres` basado en `postgis/postgis:15-3.5` a `compose.yaml`, volumen persistente, credenciales por variables de entorno y montaje de `db/init/`
- [X] T011 Configurar en `compose.yaml` red interna, healthchecks y reintentos de conexión para que PostgreSQL y Kafka sean dependencias saludables, no solo dependencias de arranque
- [X] T012 Verificar que `docker compose up --build -d` levanta únicamente los cinco servicios locales `postgres`, `kafka`, `producer`, `consumer` y `api` definidos por la constitución

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

- [X] T013 [US1] Implementar el upsert transaccional condicionado por `updated` en `consumer/app/persistence.py`: actualizar solo cuando `excluded.updated > fact_sismos.updated` y conservar una única fila por `external_id`
- [X] T014 [US1] Implementar la inserción auditable en `cuarentena` en `consumer/app/persistence.py`, conservando payload, `source_topic`, partición, offset, dimensión de calidad y motivo concreto

### Producer

- [X] T015 [P] [US1] Implementar la descarga del feed GeoJSON `earthquakes_feed.geojson` con `requests` y manejo explícito de feed inaccesible, vacío o malformado en `producer/app/feed.py`
- [X] T016 [US1] Implementar el ciclo configurable de 60 segundos en `producer/app/main.py`, extrayendo cada `feature`, conservando atributos/geometría y publicando JSON con clave estable `id` en `terremotos_raw`
- [X] T017 [US1] Implementar reintentos observables de conexión/publicación Kafka en `producer/app/main.py` sin descartar features silenciosamente

### Consumer

- [X] T018 [P] [US1] Implementar validaciones WAF en `consumer/app/quality.py`: magnitud no nula y numérica, `longitude` en `[-180, 180]`, `latitude` en `[-90, 90]`, coordenadas finitas, e `id`/`updated` presentes
- [X] T019 [P] [US1] Implementar el mapeo de fallos a las 7 dimensiones de calidad en `consumer/app/quality.py`, usando Completitud para nulos, Validez para coordenadas erróneas, Frescura para timestamps no permitidos y códigos estables para cada motivo
- [X] T020 [P] [US1] Implementar carga única de `paises.geojson` y cruce Point in Polygon con GeoPandas/`shapely` en `consumer/app/spatial.py`, devolviendo país, continente y subregión
- [X] T021 [US1] Garantizar en `consumer/app/spatial.py` que cualquier punto sin polígono terrestre recibe exactamente `Sin país asignado` y nunca el país más cercano
- [X] T022 [US1] Implementar el consumidor de `terremotos_raw` con `enable_auto_commit=False` en `consumer/app/main.py`, separando parseo, WAF, enriquecimiento y persistencia
- [X] T023 [US1] Coordinar en `consumer/app/main.py` la transacción PostgreSQL y Kafka: commit DB de upsert o cuarentena primero, `consumer.commit()` después, y offset sin confirmar ante cualquier fallo previo
- [X] T024 [US1] Conservar `source_topic`, `kafka_partition`, `kafka_offset`, `external_id` y timestamps en los logs del pipeline de `consumer/app/main.py` para auditar reintentos y replay

### Docker

- [X] T025 [US1] Crear `producer/Dockerfile` con `python:3.11-slim`, instalación de `producer/requirements.txt` y ejecución de `producer/app/main.py`
- [X] T026 [US1] Crear `consumer/Dockerfile` con `python:3.11-slim`, dependencias GeoPandas/`shapely`, montaje de `paises.geojson` y ejecución de `consumer/app/main.py`
- [X] T027 [US1] Añadir `producer` y `consumer` a `compose.yaml` con `depends_on` saludable para Kafka/PostgreSQL, variables de topics y volumen de datos espaciales

**Checkpoint**: La historia P1 funciona de extremo a extremo desde USGS hasta
PostgreSQL/cuarentena y puede demostrarse sin API.

---

## Phase 4: User Story 2 - Consultar eventos y estadísticas (Priority: P2)

**Goal**: Exponer eventos filtrables, estadísticas y GeoJSON para Angular/Leaflet
desde PostgreSQL.

**Independent Test**: Con datos conocidos en `fact_sismos`, comprobar filtros
combinables, respuestas vacías, errores de parámetros y las tres respuestas REST.

### API

- [X] T028 [P] [US2] Crear modelos de consulta y respuesta en `api/app/schemas.py` para filtros ISO, magnitud, paginación, eventos, conteos y `FeatureCollection`
- [X] T029 [P] [US2] Implementar pool `asyncpg` y manejo HTTP 503 en `api/app/db.py` con consultas parametrizadas y cierre limpio
- [X] T030 [US2] Implementar `GET /api/eventos` en `api/app/main.py` y `api/app/queries.py` con filtros combinables `country`, `date_from`, `date_to`, `min_magnitude`, `max_magnitude`, `limit` y `offset`
- [X] T031 [US2] Implementar la serialización GeoJSON `FeatureCollection` de `GET /api/eventos` en `api/app/main.py`, usando geometrías Point `[longitude, latitude, depth_km]` y propiedades geográficas
- [X] T032 [US2] Implementar `GET /api/estadisticas/paises` en `api/app/main.py` y `api/app/queries.py` con filtros de fecha/magnitud y conteo de `Sin país asignado`
- [X] T033 [US2] Implementar `GET /api/estadisticas/timeline` en `api/app/main.py` y `api/app/queries.py` con buckets `day`, `week` y `month`
- [X] T034 [US2] Validar rangos y fechas incompatibles en `api/app/schemas.py`, devolviendo errores claros HTTP 400/422 y colecciones vacías válidas
- [X] T035 [US2] Instalar middleware CORS en `api/app/main.py` con `CORS_ORIGINS`, wildcard para demo sin credenciales o lista explícita de Netlify/ngrok

### Docker

- [X] T036 [US2] Crear `api/Dockerfile` con `python:3.11-slim`, instalación de `api/requirements.txt` y ejecución de `uvicorn api.app.main:app`
- [X] T037 [US2] Añadir `api` a `compose.yaml` con dependencia saludable de PostgreSQL, puerto local documentado y variables `DATABASE_URL` y `CORS_ORIGINS`

### Frontend

- [X] T038 [US2] Adaptar `frontend/src/app/app.component.ts` y `frontend/public/config.json` para consumir `/api/eventos` GeoJSON, conservar el header ngrok y mostrar país/continente/subregión cuando estén disponibles

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

- [X] T039 [P] [US3] Crear el publicador de replay en `producer/app/replay.py` que lea `db/seeds/historical_2025.jsonl`, publique cada evento en `terremotos_replay` y acepte una tasa configurable
- [X] T040 [US3] Añadir validación de año 2025, contador de mensajes publicados y logging de lote/origen en `producer/app/replay.py`

### Consumer

- [X] T041 [US3] Extender `consumer/app/main.py` para suscribirse a `terremotos_raw` y `terremotos_replay`, conservando `source_topic` sin mezclar silenciosamente ambos canales
- [X] T042 [US3] Verificar que el replay usa exactamente `consumer/app/quality.py`, `consumer/app/spatial.py` y `consumer/app/persistence.py`, incluyendo cuarentena, `Sin país asignado` y upsert por `updated`

### Database

- [X] T043 [US3] Preparar `db/seeds/historical_2025.jsonl` con un lote reproducible que incluya eventos válidos, inválidos, marítimos y repetidos para la demostración

### Docker

- [X] T044 [US3] Montar `db/seeds/` y habilitar el comando de replay documentado en `compose.yaml` sin añadir un sexto servicio local

**Checkpoint**: El histórico puede procesarse de forma acelerada, trazable y
repetible sin alterar la ingesta normal.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Endurecimiento, documentación y validación transversal.

- [X] T045 [P] Documentar variables, servicios, topics y troubleshooting en `README.md` enlazando `specs/001-streaming-sismos-etl/quickstart.md`
- [X] T046 [P] Añadir logging de métricas de procesados, cuarentena, reintentos y lag en `producer/app/`, `consumer/app/` y `api/app/`
- [X] T047 [P] Revisar `compose.yaml`, Dockerfiles y requirements para confirmar ausencia de Spark, Flink, Kubernetes, Streamlit y servicios Cloud
- [X] T048 Ejecutar manualmente `docker compose up --build -d` y todos los escenarios de `specs/001-streaming-sismos-etl/quickstart.md`
- [X] T049 Verificar manualmente el cumplimiento constitucional y documentar resultados de calidad según la regla 1-10-100, sin generar informe automático

---

## Phase 7: Remediación del Specification Analysis Report

**Purpose**: Resolver los hallazgos C1, A1, U1, G1, G2, U2, I1 e I2 sin alterar
la arquitectura constitucional de cinco servicios.

- [X] T050 [C1] Actualizar `README.md` para declarar Netlify como publicación del frontend y ngrok como túnel externo requerido, con `NGROK_DOMAIN` documentado.
- [X] T051 [I2] Leer `NGROK_DOMAIN` desde variables de entorno en `api/app/config.py` y usarlo en el ciclo de vida de `api/app/main.py`, sin dominios codificados.
- [X] T052 [U1] Crear explícitamente `terremotos_raw` y `terremotos_replay` desde el healthcheck del servicio Kafka, manteniendo exactamente cinco servicios.
- [X] T053 [I1] Parametrizar el healthcheck de PostgreSQL con `POSTGRES_USER` y `POSTGRES_DB` provenientes de Compose.
- [X] T054 [A1] Formalizar `MIN_MAGNITUDE=0.0` y `MAX_MAGNITUDE=10.0` en `consumer/app/quality.py`, clasificando el incumplimiento como `Validez`.
- [X] T055 [G1][U2] Crear pruebas unitarias para las 7 dimensiones WAF, límites de magnitud y clasificación marítima `Sin país asignado`.
- [X] T056 [G1] Crear pruebas contractuales para rutas REST y CORS en `tests/contract/test_api_contract.py`.
- [X] T057 [G2] Crear `tests/integration/load_test.py` para medir tasa de éxito SC-001, p95 SC-005 y throughput de replay SC-006 con umbrales explícitos.
- [X] T058 Actualizar `.env.example` y la configuración local ignorada para incluir `NGROK_DOMAIN`, sin versionar credenciales.
- [X] T059 Implementar en `consumer/app/quality.py` la dimensión `Frescura`: rechazar `future_timestamp` más allá de 300 segundos y eventos raw con más de 7 días, permitiendo históricos replay.
- [X] T060 Propagar el topic Kafka al WAF desde `consumer/app/main.py` y ampliar el esquema SQL para auditar la dimensión `Frescura` en `cuarentena`.
- [X] T061 Crear `tests/test_e2e_real.py` para publicar simultáneamente en ambos topics y verificar mediante HTTP real GeoJSON, estadísticas por país y timeline.
- [X] T062 Configurar un listener externo `localhost:29092` en Kafka para que la prueba E2E real del host pueda publicar mientras Producer y Consumer usan `kafka:9092`.

**Resultado global de remediación: [OK PASS]**. La prueba E2E real y las métricas
cuantitativas se ejecutaron con el stack Compose activo.

---

## Phase 8: Cobertura integral del enunciado y materiales anexados

**Purpose**: Resolver los hallazgos de la auditoría de `enunciadoProyecto` y
alinear implementación, contratos, evidencias y frontend con el 100% de los
requisitos académicos, sin modificar la arquitectura constitucional de cinco
servicios.

### US1 — Ingesta, publicación y modelo histórico

- [X] T063 [US1] Alinear `USGS_FEED_URL` con `all_day.geojson`, filtrar `properties.type == "earthquake"` y publicar el envelope con `source`, `ingested_at`, `mode`, `id`, `updated` y el evento original en `producer/app/config.py`, `producer/app/feed.py`, `producer/app/main.py` y `.env.example`; añadir pruebas en `tests/unit/test_feed.py`
- [X] T064 [US1] Implementar estado persistente de versiones publicadas por `(external_id, updated)` en `db/init/004_ingestion_state.sql`, `producer/app/persistence.py` y `producer/app/main.py`, de modo que se publiquen solo eventos nuevos o revisiones posteriores y el estado sobreviva a reinicios; cubrirlo en `tests/integration/test_producer_state.py`
- [X] T065 [US1] Añadir historial inmutable de versiones por `(external_id, updated)` y conservar el payload original en `db/init/005_event_versions.sql` y `consumer/app/persistence.py`, manteniendo `fact_sismos` como estado actual y el commit PostgreSQL antes del offset Kafka; probar revisiones, repetición antigua y reinicio en `tests/integration/test_version_history.py`
- [X] T066 [P] [US1] Persistir y exponer `ADM0_A3`/`country_id` de Natural Earth, comprobar su unicidad y documentar la regla para fronteras o múltiples coincidencias en `consumer/app/spatial.py`, `db/init/001_schema.sql`, `consumer/app/persistence.py` y `specs/001-streaming-sismos-etl/data-model.md`; añadir casos marítimos y fronterizos en `tests/unit/test_spatial.py`
- [X] T067 [P] [US1] Implementar timeout, HTTP 429/5xx, errores JSON y reintentos con espera progresiva en `producer/app/feed.py`, conservar la última ingesta válida y documentar la recuperación tras una parada superior a 24 horas en `README.md` y `specs/001-streaming-sismos-etl/quickstart.md`

### US2 — Contrato API y frontend académico

- [X] T068 [US2] Alinear `api/app/main.py`, `api/app/schemas.py`, `api/app/queries.py` y `api/app/db.py` con `enunciadoProyecto/CONTRATO-API.md`: exponer `/api/salud`, `/api/estadisticas`, aceptar `start`, `end`, `min_mag` y `country_id`, devolver `metadata.generated`, `metadata.last_ingestion`, `mode`, `count`, `total` y `truncated`, y devolver errores explícitos de base de datos
- [X] T069 [P] [US2] Crear pruebas contractuales para el contrato anexado en `tests/contract/test_enunciado_api_contract.py`, incluyendo FeatureCollection vacía, paginación/truncado, fechas ISO inclusivas/exclusivas, valores nulos, filtros equivalentes en estadísticas, CORS exacto de Netlify y cabecera `ngrok-skip-browser-warning`
- [X] T070 [US2] Implementar en `frontend/src/app/app.component.ts`, `frontend/src/app/app.component.html` y estilos asociados filtros sincronizados de fecha/magnitud/país, tabla accesible, recuentos por país/subregión y hora UTC, distribuciones de magnitud/profundidad, comparación con la media diaria de 2025 y estado visible de API/última ingesta/truncado
- [X] T071 [P] [US2] Añadir datos de `magType`, `country_id`, `country_name`, `last_ingestion`, `mode` y registros sin valor al modelo GeoJSON del frontend y validar su representación en `tests/contract/test_frontend_contract.py` y `frontend/src/app/app.component.ts`

### US3 — Replay, calidad, rendimiento y evaluación

- [X] T072 [US3] Documentar en `db/seeds/README.md` el alcance del fixture 2025, la consulta reproducible del histórico completo, fecha/filtros/conteos esperados y verificar que `producer/app/replay.py` no trunca resultados
- [X] T073 [P] [US3] Ampliar `tests/integration/load_test.py` y `tests/integration/benchmark_scaling.py` para medir al menos tres tamaños de entrada, memoria, latencia, throughput, búsqueda secuencial frente a diccionario y consulta indexada opcional, separando datos sintéticos de los reales
- [X] T074 [P] [US3] Crear el apartado manual de calidad en `docs/calidad.md` o el notebook equivalente, con consultas/código, fuente, periodo, denominadores, resultados antes/después, completitud, unicidad, validez, consistencia, actualidad y exactitud, aplicando la regla 1-10-100 sin generar un informe automático
- [X] T075 [P] [US3] Crear `docs/evaluacion-financiera.md` con supuestos, flujos de caja, horizonte, tasa de descuento, NPV, IRR y WACC; declarar viabilidad únicamente si `NPV > 0` e `IRR > WACC`, sin usar ROI simple como criterio principal
- [X] T076 Ejecutar la validación final de `enunciadoProyecto` en `tests/test_enunciado_compliance.py`, `specs/001-streaming-sismos-etl/quickstart.md` y `README.md`: Compose con cinco servicios, all_day, contrato API, replay documentado, historial, ADM0_A3, frontend, benchmarks, evidencia manual y ausencia de tecnologías prohibidas
- [X] T077 [US3] Descargar y documentar el año completo más antiguo disponible en USGS mediante `producer/app/history.py`, generar `db/seeds/historical_1900.jsonl` y permitir replay de años históricos mediante `producer/app/replay.py --year`

**Checkpoint**: El proyecto cubre el enunciado base, el contrato API anexo, la
rúbrica de frontend, la trazabilidad histórica, la evidencia manual de calidad y
la evaluación financiera constitucional; la entrega solo puede declararse lista
cuando T063–T076 estén marcadas `[X]` y sus pruebas pasen.

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
- **Phase 8 Cobertura integral**: depende de Phase 6 y de las remediaciones T050–T062;
  T063–T067 deben completarse antes de T068–T071, y T072–T076 requieren el pipeline
  y el contrato API alineados.

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
- En Phase 8: T066-T067, T069, T071, T073-T075 pueden ejecutarse en paralelo una
  vez disponibles sus contratos y datos; T064-T065, T068 y T070 son secuenciales
  por modificar estado, persistencia y contrato compartido.

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
5. **Cobertura del enunciado**: completar Phase 8, ejecutar la matriz de
   cumplimiento y no emitir el veredicto final hasta validar T076.

### Task Format Validation

Todas las tareas usan checkbox `- [ ]`, identificador secuencial `T###`, marcador
`[P]` solo cuando son paralelizables, etiqueta `[US#]` en fases de historia y una
ruta de archivo concreta. Las tareas fundacionales y de polish no llevan etiqueta de
historia, conforme al formato requerido.
