---

description: "Task list for feature 002: platform and data model"
---

# Tasks: Plataforma y modelo de datos del observatorio

**Input**: Design documents from `/specs/002-platform-data-model/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/database.md](contracts/database.md),
[contracts/runtime.md](contracts/runtime.md), [quickstart.md](quickstart.md)

**Tests**: incluidas. El principio IX de la constitución exige pruebas de comportamiento y
evidencia ejecutada, y el plan fija las pruebas del modelo antes de su implementación.

**Organization**: tareas agrupadas por historia de usuario. La historia 2 (modelo) va antes que
la historia 1 (arranque) aunque ambas son P1, porque los servicios no pueden arrancar sanos
contra un modelo que no existe.

**Reglas para quien implemente**: código, nombres de fichero, tablas, columnas y comentarios en
inglés; documentación en español. Ninguna tarea cambia reglas de validación, endpoints ni
lógica de ingesta: eso pertenece a las specs 003, 004 y 006. Única excepción: las dos garantías
de offset de [research.md](research.md) §R20, que se corrigen en T037.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: puede hacerse en paralelo (ficheros distintos, sin dependencias pendientes)
- **[Story]**: historia de usuario de [spec.md](spec.md) a la que pertenece

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: retirar lo que el modelo nuevo sustituye y preparar la estructura

- [X] T001 Eliminar con `git rm` los ficheros del modelo anterior `db/init/001_schema.sql`, `db/init/002_seed_dimensions.sql`, `db/init/003_freshness_quarantine.sql`, `db/init/004_ingestion_state.sql`, `db/init/005_event_versions.sql`, `db/init/006_mag_type.sql` y las pruebas que solo buscan texto en el código: `tests/contract/test_enunciado_api_contract.py`, `tests/contract/test_frontend_contract.py`, `tests/test_enunciado_compliance.py`
- [X] T002 [P] Crear la estructura vacía: `db/sql/`, `common/__init__.py`, `tests/db/__init__.py`, `tests/benchmark/__init__.py`, `tests/startup/`, `docs/evidence/002/.gitkeep`
- [X] T003 [P] Ampliar `.dockerignore` con `data/`, `resources/`, `docs/`, `db/seeds/*.jsonl` y `*.md`, de modo que ninguna imagen incluya conjuntos de datos ni documentación
- [X] T004 [P] Crear `producer/requirements.in` (aiokafka==0.12.0, asyncpg==0.30.0, requests==2.32.3), `consumer/requirements.in` (aiokafka==0.12.0, asyncpg==0.30.0, geopandas==1.0.1, shapely==2.0.6), `api/requirements.in` (fastapi==0.115.6, uvicorn[standard]==0.34.0, pydantic==2.10.4, asyncpg==0.30.0) y `tests/requirements.in` (pytest, psycopg[binary], más las de los tres servicios); generar cada `requirements.txt` con todas las transitivas fijadas ejecutando `pip-compile` dentro de `python:3.11.10-slim-bookworm`. No deben quedar `psycopg2-binary`, `pydantic-settings`, `geoalchemy2` ni `ngrok`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: configuración, inicialización de la base, dimensiones y arnés de pruebas que usan
todas las historias

**⚠️ CRITICAL**: ninguna historia puede empezar antes de terminar esta fase

- [X] T005 Reescribir `.env.example` con todas las variables de [contracts/runtime.md](contracts/runtime.md), valores de ejemplo no secretos (`CAMBIAR_EN_LOCAL` en `POSTGRES_PASSWORD`, `DB_WRITER_PASSWORD` y `DB_READER_PASSWORD`), `USGS_FEED_URL` apuntando a `all_day.geojson`, `CORS_ORIGINS=https://TU-SITIO.netlify.app,http://localhost:4200` y `NGROK_AUTHTOKEN` y `NGROK_DOMAIN` vacíos
- [X] T006 Actualizar el `.env` local (no versionado) para que tenga todas las variables de `.env.example`: añadir las que falten con valores locales, corregir `USGS_FEED_URL` si apunta a `all_hour.geojson`, y no mostrar ni registrar el contenido del fichero; comprobar con `git check-ignore .env` que sigue ignorado
- [X] T007 Crear `db/sql/010_roles_schemas.sql`: esquemas `core` y `replay`; roles `observatory_writer` y `observatory_reader` con `LOGIN` y contraseña tomada de las variables de `psql` `writer_password` y `reader_password`, creados de forma idempotente (bloque `DO` que comprueba `pg_roles`); `REVOKE ALL ON SCHEMA public FROM PUBLIC`
- [X] T008 Crear `db/sql/020_dimensions.sql`: tabla `core.dim_country` (`country_id text PRIMARY KEY`, `name_es text NOT NULL`, `admin_name text NOT NULL`, `continent text NOT NULL`, `subregion text NOT NULL`, `iso_a3 text` nulo) cargada en una sola sentencia con `pg_read_file(:'catalog_path')` y `jsonb_array_elements` desde las propiedades `ADM0_A3`, `NAME_ES`, `ADMIN`, `CONTINENT`, `SUBREGION`, `ISO_A3` (guardar `-99` como nulo); tabla `core.dim_date` (`date_id date PRIMARY KEY`, `year`, `quarter`, `month`, `day`, `iso_week`, `iso_dow`, `day_of_year`, todas `smallint NOT NULL`) con un día por fila de 1900-01-01 a 2035-12-31
- [X] T009 Crear `db/sql/030_extraction.sql` con `core.extraction` (columnas de [data-model.md](data-model.md): `extraction_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY`; `source` en `usgs_feed`/`usgs_catalog`; `purpose` en `live`/`historical_load`/`gap_recovery`/`replay_selection`; `request_url text NOT NULL`; `request_params jsonb`; `window_start`, `window_end`; `requested_at timestamptz NOT NULL`; `duration_ms`; `attempt_count smallint NOT NULL DEFAULT 1`; `http_status`; `outcome` en `ok`/`not_modified`/`http_error`/`timeout`/`invalid_json`/`invalid_structure`; `error_detail`; `source_generated_at`; `record_count`, `earthquake_count`, `excluded_count`, `published_count`; `content_sha256`) y `core.raw_payload` (`content_sha256 text PRIMARY KEY`, `encoding` en `gzip`/`file`, `body bytea`, `file_path text`, `byte_size integer NOT NULL`, `first_seen_at`, `last_seen_at`, `CHECK (body IS NOT NULL OR file_path IS NOT NULL)`)
- [X] T010 Crear `db/sql/apply.sh` (recibe el nombre de la base; se conecta con las variables estándar `PGHOST`, `PGPORT`, `PGUSER` y `PGPASSWORD` si están definidas, de modo que sirve tanto dentro del contenedor de PostgreSQL como desde el contenedor de pruebas; ejecuta con `psql -v ON_ERROR_STOP=1` los ficheros existentes de `db/sql/` en orden numérico pasando `catalog_path`, `writer_password` y `reader_password`; los ficheros de plantilla, que son `040_event_tables.sql` y `060_indexes.sql`, se ejecutan una vez con `-v schema=core` y otra con `-v schema=replay`; no contiene SQL propio) y `db/init/00-init.sh` (llama a `apply.sh "$POSTGRES_DB"`); ambos con permiso de ejecución y `set -euo pipefail`
- [X] T011 Reescribir solo el servicio `postgres` de `compose.yaml`: imagen `postgres:16.4`, sin `ports`, volumen `postgres_data`, montajes de solo lectura `./db/init:/docker-entrypoint-initdb.d`, `./db/sql:/sql` y `./frontend/public/datos/paises.geojson:/catalog/paises.geojson`, variables `DB_WRITER_PASSWORD` y `DB_READER_PASSWORD`, `restart: unless-stopped` y comprobación de salud que conecte por TCP (`-h 127.0.0.1`) y ejecute `SELECT 1 FROM core.dim_country LIMIT 1`
- [X] T012 Crear `tests/Dockerfile` (base `python:3.11.10-slim-bookworm`, paquete `postgresql-client`, dependencias de `tests/requirements.txt`) y `compose.dev.yaml` con el servicio `tests` (misma red, depende de `postgres` sano, monta el repositorio en solo lectura salvo `docs/evidence/`, recibe las credenciales del propietario y además `DB_WRITER_PASSWORD` y `DB_READER_PASSWORD`)
- [X] T013 Recrear el volumen de la base: `docker compose down -v` y `docker compose up -d postgres`, y esperar a que esté sano. **Requiere confirmación de la usuaria**: borra la base local, y es imprescindible porque `postgres:16.4` no arranca sobre el directorio de datos de PostgreSQL 15 que existe ahora
- [X] T014 Crear `tests/db/conftest.py`: fixture de sesión que elimina y crea la base `observatory_test` y le aplica `db/sql/apply.sh`; fixture por prueba que vacía las tablas de eventos de `core` y `replay`; fixtures de conexión como propietario, `observatory_writer` y `observatory_reader` con `search_path` configurable
- [X] T015 Crear `tests/db/test_dimensions.py`: 177 países, exactamente 5 con `iso_a3` nulo, ninguna columna obligatoria vacía; insertar un `country_id` repetido falla por la clave primaria; `dim_date` con 49.673 filas, mínimo 1900-01-01, máximo 2035-12-31 y sin huecos; y ejecutar `docker compose -f compose.yaml -f compose.dev.yaml run --rm tests pytest tests/db/test_dimensions.py` hasta que pase

**Checkpoint**: la base se crea sola desde cero y las pruebas del modelo pueden ejecutarse

---

## Phase 3: User Story 2 - Un modelo que impide duplicar y retroceder (Priority: P1) 🎯 MVP

**Goal**: una fila por terremoto, una por versión, y una versión antigua nunca sustituye a una
más reciente, garantizado por la base

**Independent Test**: `pytest tests/db/test_event_versions.py tests/db/test_event_constraints.py tests/db/test_idempotency.py tests/db/test_roles.py` en verde (V4, V5 y V7 de [quickstart.md](quickstart.md))

### Tests for User Story 2

> Escribir primero y comprobar que FALLAN antes de implementar

- [X] T016 [P] [US2] Crear `tests/db/test_event_versions.py`: la secuencia de la FAQ 12 (E1 10:05 mag 4,2; repetición; E1 10:09 mag 4,6; E1 10:05 otra vez; E2 10:12 mag 3,1) devuelve `new`, `duplicate`, `revised`, `duplicate`, `new` y deja 2 filas en `event_current`, 3 en `event_version` y E1 con magnitud 4,6; una versión con `updated_at` anterior y nunca vista devuelve `stale`, se añade al historial y no cambia el estado actual; `first_ingested_at` no cambia en una revisión e `ingested_at` sí; cada versión conserva su `source`; y `publish_state` no retrocede cuando se le escribe un `updated_at` anterior al almacenado
- [X] T017 [P] [US2] Crear `tests/db/test_event_constraints.py`: se aceptan magnitud, tipo de magnitud, profundidad, lugar y país nulos; se aceptan magnitud negativa y profundidad negativa; se rechazan longitud fuera de [−180, 180], latitud fuera de [−90, 90], NaN e infinito en magnitud, profundidad y coordenadas, `source` distinto de `usgs_feed` o `usgs_catalog` y `country_id` inexistente; `event_date` es el día UTC de `event_time` (`2026-10-28 00:30+02` → `2026-10-27`) y cambia cuando una revisión cambia `event_time`; `replayed_at` debe ser nulo en `core` y no nulo en `replay`
- [X] T018 [P] [US2] Crear `tests/db/test_idempotency.py`: procesar 1.000 veces un mismo conjunto de 50 mensajes (versiones, revisiones y rechazos, cada uno con su topic, partición y offset) y comprobar que los recuentos de `event_current`, `event_version`, `quarantine` y `message_log` son idénticos a los de la primera pasada

### Implementation for User Story 2

- [X] T019 [US2] Crear `db/sql/040_event_tables.sql` como plantilla sobre la variable `schema` con `event_current` y `event_version` exactamente como en [data-model.md](data-model.md) §3. `event_current`: `event_id text PRIMARY KEY`; `source text NOT NULL CHECK (source IN ('usgs_feed','usgs_catalog'))`; `event_time timestamptz NOT NULL`; `event_date date GENERATED ALWAYS AS ((event_time AT TIME ZONE 'UTC')::date) STORED REFERENCES core.dim_date`; `updated_at timestamptz NOT NULL`; `magnitude`, `depth_km` `double precision` nulos; `mag_type`, `place` `text` nulos; `longitude double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180)`; `latitude double precision NOT NULL CHECK (latitude BETWEEN -90 AND 90)`; `country_id text REFERENCES core.dim_country` nulo; `quality_flags text[] NOT NULL DEFAULT '{}'`; `first_ingested_at` e `ingested_at` `timestamptz NOT NULL DEFAULT now()`; `replayed_at timestamptz`; `CHECK` que impidan NaN e infinito; sin mínimo para magnitud ni profundidad. `event_version`: `event_id text NOT NULL` con clave foránea a `event_current` y `ON DELETE CASCADE`; `updated_at timestamptz NOT NULL`; `PRIMARY KEY (event_id, updated_at)`; `source text NOT NULL` con el mismo `CHECK`; `event_time timestamptz NOT NULL`; `magnitude`, `depth_km` `double precision` nulos; `mag_type text` nulo; `longitude` y `latitude` `double precision NOT NULL`; `payload jsonb NOT NULL`; `received_at timestamptz NOT NULL DEFAULT now()`; `kafka_topic text NOT NULL`, `kafka_partition integer NOT NULL`, `kafka_offset bigint NOT NULL`
- [X] T020 [US2] Añadir a `db/sql/040_event_tables.sql` las tablas `publish_state` (`event_id text PRIMARY KEY`, `updated_at timestamptz NOT NULL`, `published_at timestamptz NOT NULL DEFAULT now()`); `quarantine` (`quarantine_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY`; `kafka_topic text`, `kafka_partition integer`, `kafka_offset bigint`, los tres `NOT NULL` y `UNIQUE` en conjunto; `event_id text` nulo; `reason_codes text[] NOT NULL CHECK (cardinality(reason_codes) > 0)`; `reason_detail text NOT NULL`; `payload jsonb` y `raw_text text` con `CHECK (payload IS NOT NULL OR raw_text IS NOT NULL)`; `is_synthetic boolean NOT NULL DEFAULT false`; `quarantined_at timestamptz NOT NULL DEFAULT now()`); `excluded_event` (`event_id text`, `updated_at timestamptz`, `PRIMARY KEY` conjunta; `event_type text` nulo; `reason_code text NOT NULL DEFAULT 'not_earthquake'`; `extraction_id bigint REFERENCES core.extraction` nulo; `payload jsonb NOT NULL`; `first_seen_at timestamptz NOT NULL DEFAULT now()`); y `message_log` (`kafka_topic text`, `kafka_partition integer`, `kafka_offset bigint`, `PRIMARY KEY` conjunta; `event_id text` nulo; `updated_at timestamptz` nulo; `outcome text NOT NULL CHECK (outcome IN ('new','revised','stale','duplicate','quarantined'))`; `produced_at timestamptz` nulo; `processed_at timestamptz NOT NULL DEFAULT now()`)
- [X] T021 [US2] Añadir a `db/sql/040_event_tables.sql` la función `apply_event_version` con la firma de [contracts/database.md](contracts/database.md), `SET search_path` al esquema de la plantilla seguido de `core`, que hace el upsert de `event_current` con `WHERE EXCLUDED.updated_at > event_current.updated_at` (sin modificar `first_ingested_at`), inserta en `event_version` con `ON CONFLICT DO NOTHING` y devuelve `new`, `revised`, `stale` o `duplicate`
- [X] T022 [US2] Crear `db/sql/050_schema_rules.sql` con las reglas que difieren entre esquemas: `CHECK (replayed_at IS NULL)` en `core.event_current` y `NOT NULL` en `replay.event_current.replayed_at`
- [X] T023 [US2] Crear `db/sql/070_grants.sql` (`observatory_writer`: `USAGE` en `core` y `replay`, `SELECT, INSERT, UPDATE, DELETE` en sus tablas, `EXECUTE` en `apply_event_version`, sin DDL; `observatory_reader`: `USAGE` y `SELECT`; privilegios por defecto para tablas futuras) y `tests/db/test_roles.py` (el lector no puede insertar, actualizar ni borrar; el escritor no puede crear ni eliminar tablas; ambos pueden leer `dim_country`)
- [X] T024 [US2] Ejecutar `pytest tests/db -v` en el contenedor `tests`, corregir hasta que todo pase y guardar la salida en `docs/evidence/002/db-tests.txt`

**Checkpoint**: el modelo garantiza por sí solo los resultados de la FAQ 12

---

## Phase 4: User Story 1 - Levantar el sistema desde un clon limpio (Priority: P1)

**Goal**: `docker compose up --build -d` deja los cinco servicios sanos, con solo la API
accesible desde el propio equipo y un evento real recorriendo el sistema sobre el modelo nuevo

**Independent Test**: escenarios V1, V2, V8, V9, V10 y V12 de [quickstart.md](quickstart.md)

### Tests for User Story 1

- [ ] T025 [P] [US1] Crear `tests/unit/test_common_retry.py` (la espera crece de forma exponencial desde 1 s, no supera 30 s y reintenta hasta que la operación tiene éxito), `tests/unit/test_common_settings.py` (una variable obligatoria ausente produce un error que la nombra; `CORS_ORIGINS=*` se rechaza) y `tests/unit/test_common_health.py` (un latido reciente es sano y uno con más de tres intervalos no)
- [ ] T026 [P] [US1] Crear `tests/unit/test_consumer_loop.py` con un consumidor de Kafka simulado: el consumidor se configura con confirmación automática desactivada y con inicio en el principio del topic cuando el grupo no tiene offsets; si procesar un mensaje falla, no se confirma ese offset ni ninguno posterior y el mismo mensaje se reintenta; cuando el reintento tiene éxito se confirma y se continúa; un mensaje enviado a cuarentena cuenta como procesado y sí confirma su offset

### Implementation for User Story 1

- [ ] T027 [P] [US1] Crear `common/settings.py`: lectura tipada de todas las variables de [contracts/runtime.md](contracts/runtime.md), error que nombra la variable que falta, construcción del DSN por rol y validación de que `CORS_ORIGINS` es una lista de orígenes exactos
- [ ] T028 [P] [US1] Crear `common/logging.py` (formato único con hora UTC, nivel y servicio) y `common/retry.py` (reintento asíncrono con espera exponencial de 1 s a 30 s, sin límite de intentos, registrando cada fallo)
- [ ] T029 [P] [US1] Crear `common/db.py`: creación de un pool `asyncpg` con reintentos y `search_path` fijado en cada conexión mediante `server_settings`
- [ ] T030 [P] [US1] Crear `common/topics.py`: creación idempotente de `earthquakes.live`, `earthquakes.catalog` y `earthquakes.replay` con el cliente de administración de `aiokafka` (1 partición, `retention.ms` derivado de `KAFKA_RETENTION_HOURS`), y la función que devuelve el `search_path` de destino para cada topic (`core` para los dos primeros, `replay, core` para el tercero) y falla con un topic desconocido
- [ ] T031 [P] [US1] Crear `common/health.py`: escritura del fichero de latido y orden `python -m common.health --max-age <segundos>` que termina con código distinto de cero si el latido es antiguo o no existe
- [ ] T032 [P] [US1] Reescribir `producer/Dockerfile`: base `python:3.11.10-slim-bookworm`, usuario sin privilegios, instalación desde `producer/requirements.txt`, copia de `common/` y `producer/app/`, sin copiar `db/seeds`
- [ ] T033 [P] [US1] Reescribir `consumer/Dockerfile` con las mismas reglas, copiando `common/` y `consumer/app/`
- [ ] T034 [P] [US1] Reescribir `api/Dockerfile` con las mismas reglas, copiando `common/` y `api/app/`, con Uvicorn en `0.0.0.0:8000`
- [ ] T035 [US1] Completar `compose.yaml` según [contracts/runtime.md](contracts/runtime.md): `kafka` (`confluentinc/cp-kafka:7.7.1`, KRaft, un único listener interno `kafka:9092`, sin `ports`, volumen `kafka_data`, `KAFKA_AUTO_CREATE_TOPICS_ENABLE: "false"`, `KAFKA_LOG_RETENTION_HOURS` desde `KAFKA_RETENTION_HOURS`, salud con `kafka-broker-api-versions`); `producer` y `consumer` (dependen de `kafka` y `postgres` sanos, salud con `python -m common.health`, catálogo y `data/` montados en solo lectura); `api` (depende de `postgres` sano, `ports: ["127.0.0.1:8000:8000"]`, salud con `GET /api/salud`); `tunnel` (`ngrok/ngrok:3.18.4-alpine`, `profiles: ["tunnel"]`, apunta a `http://api:8000`, `NGROK_AUTHTOKEN` y `NGROK_DOMAIN` desde el entorno); `restart: unless-stopped` en todos; cada servicio recibe solo las variables que necesita en lugar de `env_file` completo
- [ ] T036 [US1] Adaptar el productor al modelo nuevo sin cambiar su lógica: `producer/app/config.py` usa `common/settings.py`; `producer/app/persistence.py` pasa a `asyncpg`, deja de crear tablas y lee y escribe `publish_state` con una sola conexión del pool; `producer/app/main.py` crea los topics, publica en `earthquakes.live`, reintenta con `common/retry.py` y actualiza el latido tras cada ciclo correcto
- [ ] T037 [US1] Adaptar el consumidor al modelo nuevo sin cambiar sus reglas de validación: eliminar `ensure_schema` de `consumer/app/persistence.py`; pasar a `asyncpg`; seguir la transacción por mensaje de [contracts/database.md](contracts/database.md) (evento válido con `apply_event_version` o rechazo en `quarantine` con `ON CONFLICT DO NOTHING` y todos los motivos en `reason_codes`, más la fila de `message_log` con el resultado y con `produced_at` tomado del `ingested_at` del mensaje, todo con el `search_path` del topic); `consumer/app/spatial.py` devuelve `country_id` nulo cuando no hay polígono en lugar del texto «Sin país asignado»; `consumer/app/main.py` crea los topics, se suscribe a los tres, empieza por el principio del topic si el grupo no tiene offsets, reintenta con espera el mismo mensaje cuando falla sin confirmar offsets posteriores, y actualiza el latido; `tests/unit/test_consumer_loop.py` debe pasar
- [ ] T038 [US1] Adaptar la API al modelo nuevo sin añadir endpoints: quitar `ngrok` de `api/app/main.py`; `api/app/db.py` usa `common/db.py` con el rol `observatory_reader`; `api/app/queries.py` consulta `event_current` con `LEFT JOIN dim_country`; `api/app/schemas.py` admite `mag`, `country` y `country_id` nulos; `GET /api/salud` responde con estado degradado si la base no está disponible; `CORS` toma los orígenes de `common/settings.py`
- [ ] T039 [US1] Actualizar o retirar las pruebas que la adaptación deja obsoletas: `tests/unit/test_statistics_filters.py`, `tests/unit/test_spatial.py`, `tests/contract/test_api_contract.py`, `tests/integration/test_producer_state.py`, `tests/integration/test_version_history.py` y `tests/test_e2e_real.py`; conservar solo las que comprueban comportamiento y pasan en el contenedor `tests`. `tests/integration/benchmark_scaling.py`, `tests/integration/load_test.py` y `tests/integration/test_load_test.py` no se tocan: se revisan en la spec 008
- [ ] T040 [US1] Reescribir en `README.md` los apartados de requisitos y versiones, creación de `.env`, arranque, comprobación de estado y logs, activación del túnel con `--profile tunnel`, ejecución de pruebas, parada, qué se conserva al reiniciar, cómo recrear la base con `docker compose down -v`, la decisión de no exponer Kafka ni PostgreSQL al equipo (un único listener interno) y la carpeta `data/` como ubicación de los originales fuera de Git; órdenes en `bash`
- [ ] T041 [US1] Validar V1, V2, V8, V9 y V10 de [quickstart.md](quickstart.md) con el sistema real y guardar resultado esperado, observado y salida en `docs/evidence/002/startup.md`. **Requiere confirmación de la usuaria**: recrea la base local con `docker compose down -v`. Comprobar aquí la sintaxis del agente de ngrok para el dominio reservado y corregir `compose.yaml` si hace falta
- [ ] T042 [US1] Ejecutar V12 (ningún fichero versionado mayor de 5 MB salvo el catálogo, ninguna credencial, ningún `node_modules`) y `docker image inspect` para confirmar que ninguna imagen contiene `db/seeds`; guardar la salida en `docs/evidence/002/repository-hygiene.txt`

**Checkpoint**: MVP. Cinco servicios sanos y un evento real de USGS visible en `GET /api/eventos`

---

## Phase 5: User Story 3 - Reproducción físicamente separada (Priority: P2)

**Goal**: los datos de reproducción no pueden modificar ni mezclarse con los reales

**Independent Test**: `pytest tests/db/test_replay_isolation.py` en verde (V6)

### Tests for User Story 3

- [X] T043 [P] [US3] Crear `tests/db/test_replay_isolation.py`: el mismo `event_id` con magnitudes distintas en `core` y `replay` conserva cada valor; insertar 10.000 eventos en `replay` y llamar a `replay.reset()` deja idénticos el recuento y una suma de comprobación de `core.event_current`, `core.event_version`, `core.publish_state` y `core.message_log`; `dim_country` y `dim_date` no cambian; un evento de reproducción conserva su `event_time` original y tiene `replayed_at`; `observatory_writer` puede ejecutar `replay.reset()` y no existe una función equivalente en `core`

### Implementation for User Story 3

- [X] T044 [US3] Añadir a `db/sql/050_schema_rules.sql` la función `replay.reset()` (`SECURITY DEFINER`, `search_path` fijo, vacía `event_version`, `event_current`, `quarantine`, `excluded_event`, `publish_state` y `message_log` del esquema `replay`) y su `GRANT EXECUTE` a `observatory_writer` en `db/sql/070_grants.sql`
- [ ] T045 [US3] Crear `tests/unit/test_common_topics.py`: `earthquakes.live` y `earthquakes.catalog` se dirigen a `core`, `earthquakes.replay` a `replay, core`, y un topic desconocido produce un error en lugar de un destino por defecto

**Checkpoint**: el aislamiento está garantizado por la estructura y probado

---

## Phase 6: User Story 4 - Trazabilidad del original y de las extracciones (Priority: P2)

**Goal**: cada consulta a USGS queda registrada, los originales idénticos se guardan una vez,
cada rechazo o exclusión conserva su motivo y los mensajes recibidos se pueden contar

**Independent Test**: `pytest tests/db/test_provenance.py` en verde

### Tests for User Story 4

- [X] T046 [P] [US4] Crear `tests/db/test_provenance.py`: dos extracciones con la misma huella dejan 2 filas en `extraction` y 1 en `raw_payload` con `last_seen_at` actualizado; una extracción con `outcome = 'timeout'` se registra con `error_detail` y sin huella; `outcome` y `purpose` fuera de sus valores se rechazan; `raw_payload` exige `body` o `file_path`; `core.purge_raw_payload(7)` elimina los cuerpos con `last_seen_at` de más de 7 días, devuelve cuántos y conserva los registros de fichero y todas las extracciones; la cuarentena no admite dos filas para el mismo topic, partición y offset, ni una fila sin `payload` ni `raw_text`, ni `reason_codes` vacío; `excluded_event` no duplica el mismo `(event_id, updated_at)`, conserva `event_type` y rechaza un `extraction_id` inexistente; `message_log` rechaza un `outcome` fuera de sus valores y, tras la secuencia de la FAQ 12, contiene 5 filas de las que 2 son `duplicate`, frente a 3 versiones y 2 eventos actuales

### Implementation for User Story 4

- [X] T047 [US4] Añadir a `db/sql/030_extraction.sql` la función `core.purge_raw_payload(retention_days integer) RETURNS integer`, que elimina de `raw_payload` las filas con `body` no nulo y `last_seen_at` anterior a la retención, y su `GRANT EXECUTE` a `observatory_writer` en `db/sql/070_grants.sql`
- [ ] T048 [US4] Reescribir `db/seeds/README.md`: retirar la descripción de `historical_2026.jsonl`, explicar que los conjuntos descargados se guardan en `data/` fuera de Git, que su huella y su ruta constan en `core.raw_payload`, y que el procedimiento de descarga y regeneración se define en la spec 003
- [X] T049 [US4] Ejecutar `pytest tests/db -v` completo y actualizar `docs/evidence/002/db-tests.txt`

**Checkpoint**: el modelo soporta toda la procedencia que exigirán las specs 003 y 004

---

## Phase 7: User Story 5 - Modelo explicado y optimizado con mediciones (Priority: P3)

**Goal**: diccionario de datos, modelo en tres niveles e índices justificados con medición

**Independent Test**: V11 de [quickstart.md](quickstart.md) reproduce la tabla de mediciones y
`pytest tests/db/test_data_dictionary.py` pasa

### Tests for User Story 5

- [ ] T050 [P] [US5] Crear `tests/db/test_data_dictionary.py`: toda columna de las tablas de `core` y `replay` que devuelve `information_schema.columns` aparece documentada en `docs/report.md`, y el documento no describe columnas que no existen

### Implementation for User Story 5

- [ ] T051 [US5] Crear `tests/benchmark/index_benchmark.py`: crea el esquema `bench` con la plantilla `db/sql/040_event_tables.sql`; genera 10.000, 100.000 y 1.000.000 de eventos sintéticos repartidos de forma uniforme en un año, con países tomados de `dim_country` más un 30 % sin país, magnitudes entre 1 y 8 con más eventos pequeños que grandes y un 5 % de revisiones; mide con `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` la mediana de 5 ejecuciones y los búferes leídos, sin y con cada índice candidato de [research.md](research.md) §R11, de cinco consultas (últimas 24 h; intervalo de un mes agrupado por hora UTC; país más intervalo; `magnitude >= 4` sobre el año completo; versiones de un `event_id`, esta comparada contra una copia de `event_version` sin clave primaria); registra el tamaño de cada índice; escribe una tabla Markdown en `docs/evidence/002/index-benchmark.md` con equipo, fecha y procedimiento; y elimina `bench` al terminar, también si falla
- [ ] T052 [US5] Ejecutar la medición, conservar solo los índices secundarios cuya consulta es al menos 2 veces más rápida en mediana con 1.000.000 de filas, y crear `db/sql/060_indexes.sql` como plantilla por esquema con los supervivientes más el índice parcial de `core.extraction` para `last_ingestion` si supera su medición; cada índice lleva un comentario SQL con la consulta que resuelve
- [ ] T053 [US5] Crear `docs/report.md` con los apartados de esta funcionalidad: alcance y decisiones (histórico 2025 mundial con magnitud ≥ 4, material de apoyo reutilizado frente a desarrollado), diccionario de datos (significado, tipo o unidad, conversión y tratamiento de ausencias de cada campo), modelo conceptual con diagrama Mermaid, modelo lógico (grano, claves y relaciones), modelo físico con enlaces a `db/sql/`, justificación de cada índice con su medición sin y con índice, índices descartados y por qué, y razonamiento sobre 100 millones de registros apoyado en la tendencia medida
- [ ] T054 [US5] Ejecutar `pytest tests/db/test_data_dictionary.py` y corregir `docs/report.md` hasta que pase

**Checkpoint**: el criterio de modelado tiene evidencia de nivel sobresaliente

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T055 Crear `tests/startup/cold_start.sh`, que construye las imágenes una vez y después repite diez veces `docker compose down -v` y `docker compose up -d` midiendo el tiempo hasta que los cinco servicios están sanos, y guardar el resultado en `docs/evidence/002/cold-starts.md` (SC-002). **Requiere confirmación de la usuaria**: borra la base local en cada iteración
- [ ] T056 Recorrer V1 a V12 de [quickstart.md](quickstart.md) y completar `docs/evidence/002/README.md` con una tabla de escenario, resultado esperado, resultado observado y enlace a la evidencia; no marcar ninguno como superado sin haberlo ejecutado
- [ ] T057 [P] Pedir a una persona ajena al proyecto que levante el sistema siguiendo solo `README.md` y anotar el tiempo y las dudas en `docs/evidence/002/README.md` (SC-001); corregir el README con lo que falle
- [ ] T058 Revisar el cumplimiento de la constitución v2.1.0 (principios I, II, III, V, VI, IX e idioma), actualizar `specs/002-platform-data-model/checklists/requirements.md` y confirmar que `git status` no muestra ficheros de datos, `.env` ni credenciales antes de cualquier commit

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias
- **Foundational (Phase 2)**: depende de Setup; bloquea todas las historias
- **US2 (Phase 3)**: depende de Foundational
- **US1 (Phase 4)**: depende de US2, porque los servicios escriben en `event_current`, `quarantine`, `message_log` y `publish_state`
- **US3 (Phase 5)**: depende de US2; independiente de US1
- **US4 (Phase 6)**: depende de US2; independiente de US1 y US3
- **US5 (Phase 7)**: depende de US2; conviene hacerla después de US3 y US4 para no reescribir el diccionario
- **Polish (Phase 8)**: depende de todas

```text
Setup → Foundational → US2 ─┬→ US1 ───┐
                            ├→ US3 ───┼→ US5 → Polish
                            └→ US4 ───┘
```

### Within Each User Story

- Las pruebas se escriben y fallan antes de implementar
- `db/sql/040_event_tables.sql`: T019, T020 y T021, en ese orden
- `db/sql/030_extraction.sql`: T009 y T047
- `db/sql/050_schema_rules.sql`: T022 y T044
- `db/sql/070_grants.sql`: T023, T044 y T047
- `compose.yaml`: T011 y T035
- T013 (recrear el volumen) va antes de cualquier ejecución de pruebas

### Parallel Opportunities

- Setup: T002, T003 y T004
- US2: las tres pruebas T016, T017 y T018
- US1: T025 a T034 (pruebas, módulos de `common/` y Dockerfiles, todos en ficheros distintos)
- Tras US2, las historias US1, US3 y US4 pueden avanzar a la vez

---

## Parallel Example: User Story 1

```bash
# Módulos compartidos, en paralelo:
Task: "Crear common/settings.py"
Task: "Crear common/logging.py y common/retry.py"
Task: "Crear common/db.py"
Task: "Crear common/topics.py"
Task: "Crear common/health.py"

# Imágenes, en paralelo:
Task: "Reescribir producer/Dockerfile"
Task: "Reescribir consumer/Dockerfile"
Task: "Reescribir api/Dockerfile"
```

---

## Implementation Strategy

### MVP First (US2 + US1)

1. Setup y Foundational
2. US2: el modelo supera la secuencia de la FAQ 12
3. US1: los cinco servicios arrancan sanos sobre ese modelo
4. **Parar y validar**: V1 a V5 y V7 a V10; un evento real llega de USGS a `GET /api/eventos`

### Incremental Delivery

1. MVP
2. US3: aislamiento de la reproducción probado
3. US4: procedencia lista para la spec 003
4. US5: mediciones, índices definitivos y primeros apartados de la memoria
5. Polish: evidencias completas

### Reglas de integración

- El trabajo se hace en la rama `002-platform-data-model`; `main` no se actualiza hasta que la
  API vuelva a cumplir el contrato (spec 006) y el consumidor deje de rechazar la magnitud nula
  (spec 004), para no dejar sin datos el panel publicado
- Commit tras cada tarea o grupo lógico, con mensaje en inglés
- T013, T041 y T055 borran la base local: no ejecutarlas sin confirmación

## Notes

- Cualquier cambio de modelo en desarrollo exige recrear el volumen: los ficheros de
  inicialización solo se ejecutan con la base vacía
- Si una tarea de adaptación (T036 a T038) pide cambiar una regla de validación o añadir un
  endpoint, se detiene y se anota para la spec correspondiente
- `docs/calidad.md` y `docs/evaluacion-financiera.md` contradicen la constitución; se sustituyen
  en la spec 008, no aquí
- `core.purge_raw_payload` se crea aquí pero nadie la invoca todavía: la llamada periódica desde
  el productor corresponde a la spec 003
- Cómo marcar como sintéticos los casos controlados de duplicado y revisión de la reproducción
  se decide en la spec 005; el modelo lo permite con `quality_flags`, y
  `db/seeds/historical_2025.jsonl`, que hoy contiene 6 eventos ficticios, se renombra allí
