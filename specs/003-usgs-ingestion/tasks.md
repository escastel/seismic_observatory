---

description: "Task list for feature 003: USGS ingestion"
---

# Tasks: Ingesta desde USGS

**Input**: Design documents from `/specs/003-usgs-ingestion/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/catalog-loader.md](contracts/catalog-loader.md),
[contracts/messages.md](contracts/messages.md), [contracts/runtime.md](contracts/runtime.md),
[quickstart.md](quickstart.md)

**Tests**: incluidas. El principio IX de la constitución y FR-037 exigen pruebas de
comportamiento y evidencia ejecutada; los fallos de la fuente se prueban con una fuente simulada.

**Organization**: tareas agrupadas por historia de usuario, en orden de prioridad. US1 (feed) y
US2 (histórico) son P1 e independientes entre sí una vez terminada la fase 2.

**Reglas para quien implemente**: código, nombres de fichero, identificadores y comentarios en
inglés; documentación y evidencias en español. No se modifica `db/sql/`, `consumer/`, `api/`,
`frontend/` ni `producer/app/replay.py` (FR-035); si una tarea parece exigirlo, se detiene y se
anota. No se añade ninguna dependencia. Las pruebas se ejecutan en el contenedor `tests`
(`docker compose -f compose.yaml -f compose.dev.yaml run --rm tests pytest …`), nunca dos
ejecuciones de `tests/db` a la vez. La evidencia se guarda con la skill `verify-stack` en
`docs/evidence/003/`. Nunca leer ni imprimir `.env`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: puede hacerse en paralelo (ficheros distintos, sin dependencias pendientes)
- **[Story]**: historia de usuario de [spec.md](spec.md) a la que pertenece

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: estructura y configuración que usan todas las historias

- [X] T001 Crear la estructura vacía: `tests/support/__init__.py`, `tests/analysis/__init__.py` y `docs/evidence/003/.gitkeep`
- [X] T002 [P] Añadir a `.env.example` las variables de [contracts/runtime.md](contracts/runtime.md) con sus valores por defecto no secretos y un comentario en inglés cada una: `USGS_CATALOG_URL=https://earthquake.usgs.gov/fdsnws/event/1`, `USGS_TIMEOUT_SECONDS=30`, `USGS_MAX_ATTEMPTS=4`, `USGS_USER_AGENT=seismic-observatory/1.0`, `GAP_MARGIN_MINUTES=60`, `DATA_DIR=/data`, `LOADER_UID=0`, `LOADER_GID=0`
- [X] T003 Completar el `.env` local (no versionado) con las variables nuevas de `.env.example`, comparando solo nombres (`comm -23` sobre los nombres, como en la skill `verify-stack`) y sin mostrar ni registrar valores; comprobar con `git check-ignore .env` que sigue ignorado

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: cliente de la fuente, huella, clasificación, registro de procedencia y publicación,
que comparten el feed y la carga del catálogo

**⚠️ CRITICAL**: ninguna historia puede empezar antes de terminar esta fase

- [X] T004 Ampliar `common/settings.py` y `tests/unit/test_common_settings.py`: dataclass `UsgsSettings` (`feed_url` obligatorio desde `USGS_FEED_URL`; `catalog_url` por defecto `https://earthquake.usgs.gov/fdsnws/event/1`, sin barra final; `timeout_seconds` 30; `max_attempts` 4; `user_agent` `seismic-observatory/1.0`), `gap_margin_minutes` (60) y `data_dir` (`/data`); `ProducerSettings` pasa a incluir `usgs` y `gap_margin_minutes` conservando `feed_url`, `interval_seconds` y `raw_payload_retention_days`; función nueva `catalog_loader()` que devuelve base de datos de escritor, Kafka, `usgs`, `gap_margin_minutes` y `data_dir` sin exigir `USGS_FEED_URL`. Pruebas: valores por defecto, enteros no positivos rechazados nombrando la variable, y `catalog_loader()` funciona sin `USGS_FEED_URL`
- [X] T005 Crear `tests/support/usgs_stub.py` (solo biblioteca estándar): servidor HTTP que se arranca en un hilo con un guion por ruta, donde cada petición consume la siguiente respuesta del guion y la última se repite. Respuestas disponibles: 200 con un cuerpo dado y cabecera `Last-Modified`; 304 cuando llega `If-Modified-Since`; 429 con `Retry-After` en segundos o en fecha HTTP; 503; retraso mayor que el tiempo de espera; cuerpo que no es JSON; JSON sin `features`; y, para el catálogo, `/count` que devuelve `{"count": N, "maxAllowed": M}` y `/query` que devuelve una colección o un 400 con el texto `N matching events exceeds search limit of M`. Registra cada petición recibida (ruta, parámetros, cabeceras, instante) para que las pruebas la inspeccionen. Incluir `python -m tests.support.usgs_stub --port 8080` para ejecutarlo como servicio con rutas fijas `/feed/ok`, `/feed/fail-503`, `/feed/fail-429`, `/feed/timeout`, `/feed/not-json` y `/feed/bad-structure`. Añadir funciones auxiliares que construyen elementos `Feature` y colecciones de prueba
- [X] T006 Crear `tests/unit/test_usgs_client.py` contra la fuente simulada, antes de implementar: 200 devuelve resultado `ok` con el cuerpo en bytes, `attempt_count` 1, `duration_ms` ≥ 0 y `last_modified`; 304 devuelve `not_modified`; 503 seguido de 200 devuelve `ok` con `attempt_count` 2; 503 en todos los intentos devuelve `http_error` con `http_status` 503 y `attempt_count` igual al máximo; 429 con `Retry-After: 2` espera al menos 2 s antes del reintento (con la función de espera inyectada y registrada); `Retry-After` en fecha HTTP se convierte a segundos; `Retry-After` mayor de 120 s no se reintenta y el resultado incluye `retry_after_seconds`; tiempo agotado devuelve `timeout` con `http_status` nulo; un 400 no se reintenta; cuerpo no JSON devuelve `invalid_json`; JSON sin lista `features` o con `type` distinto de `FeatureCollection` devuelve `invalid_structure`; ningún caso lanza una excepción; la cabecera `User-Agent` enviada es la configurada y `If-Modified-Since` se envía solo cuando se pasa
- [X] T007 Crear `producer/app/usgs.py` hasta que T006 pase: función síncrona `fetch(url, params, settings, if_modified_since, sleep)` basada en `requests` que devuelve un `FetchResult` (dataclass con `outcome` en `ok`/`not_modified`/`http_error`/`timeout`/`invalid_json`/`invalid_structure`, `http_status`, `attempt_count`, `duration_ms`, `body` en bytes, `payload` ya analizado cuando es válido, `error_detail`, `last_modified`, `retry_after_seconds`, `url` final con parámetros y `requested_at`); reintenta ante tiempo agotado, error de conexión, 429 y 5xx hasta `max_attempts`, con espera de 1, 2 y 4 s o la de `Retry-After` si es mayor; con `Retry-After` > 120 s no reintenta; validación de estructura parametrizable para aceptar también la respuesta de `/count` (objeto con `count` y `maxAllowed`); una envoltura asíncrona `fetch_async` que la ejecuta con `asyncio.to_thread`
- [X] T008 [P] Crear `producer/app/fingerprint.py` y `tests/unit/test_fingerprint.py`: `features_fingerprint(features)` = SHA-256 en hexadecimal del JSON canónico (claves ordenadas, separadores `,` y `:` sin espacios, UTF-8, `ensure_ascii=False`); `bytes_fingerprint(data)`; `file_fingerprint(path)` leyendo por bloques. Pruebas: dos colecciones con los mismos elementos y distinto orden de claves dan la misma huella; cambiar un valor o el orden de los elementos la cambia; la huella no depende de `metadata`; `file_fingerprint` coincide con `hashlib.sha256` del contenido
- [X] T009 [P] Crear `producer/app/classify.py` y `tests/unit/test_classify.py`: `classify(features)` devuelve tres listas: terremotos (elementos con `id` no vacío, `properties.updated` convertible a instante y `properties.type == "earthquake"`), excluidos (identificables con otro tipo, con `reason_code` `not_earthquake`, o sin tipo, con `missing_type`) y no identificables (no son objetos, sin `id` o sin `updated` legible), cada uno con su posición en la respuesta; `updated` se convierte de milisegundos Unix a instante UTC. Pruebas: un caso de cada clase, `updated` no numérico, elemento que no es un objeto, y que la suma de las tres listas es el total recibido
- [X] T010 Crear `producer/app/provenance.py` y `tests/db/test_provenance_writes.py` (con `asyncpg` contra `observatory_test`, como `tests/db/test_consumer_persistence.py`): `record_extraction(conn, result, source, purpose, counts, fingerprint, request_params, window)` inserta en `extraction` y devuelve `extraction_id` siguiendo la tabla de [data-model.md](data-model.md) §2 (`outcome` en `ok`/`not_modified`/`http_error`/`timeout`/`invalid_json`/`invalid_structure`; `purpose` en `live`/`historical_load`/`gap_recovery`; recuentos nulos en los fallos; `source_generated_at` desde `metadata.generated`); `set_published_count(conn, extraction_id, n)`; `store_body(conn, fingerprint, body)` guarda el cuerpo con gzip y `encoding = 'gzip'` usando `ON CONFLICT (content_sha256) DO UPDATE SET last_seen_at = EXCLUDED.last_seen_at`; `store_file(conn, fingerprint, relative_path, byte_size)` con `encoding = 'file'`; `touch_payload(conn, fingerprint)`; `record_exclusions(conn, excluded, extraction_id)` con `ON CONFLICT (event_id, updated_at) DO NOTHING`; `last_successful_feed_request(conn)`. Pruebas: una fila por cada caso de la tabla; el mismo contenido dos veces deja un original con `last_seen_at` actualizado; una exclusión repetida no se duplica y conserva el primer `extraction_id`; `record_count = earthquake_count + excluded_count`
- [X] T011 Crear `producer/app/publisher.py` y `tests/db/test_publisher.py`: `build_message(feature, source, extraction_id, ingested_at)` con los campos de [contracts/messages.md](contracts/messages.md) (`id`, `updated`, `time`, `mag`, `place`, `geometry`, `properties`, `source` en `usgs_feed`/`usgs_catalog`, `ingested_at` ISO 8601 UTC, `mode` = `live`, `extraction_id`, `original_event`); `publish_versions(producer, conn, topic, earthquakes, source, extraction_id)` que consulta `publish_state`, publica solo versiones nuevas o con `updated` posterior, usa `event_id` como clave, espera la confirmación de cada envío y solo entonces marca la versión con las funciones de `producer/app/persistence.py`; devuelve cuántas publicó. Pruebas con un productor de Kafka simulado: versión nueva se publica y se marca; la misma versión no se republica; una versión anterior no se publica; si el envío falla, la versión no queda marcada y la siguiente llamada la reintenta; clave y campos del mensaje correctos; el mensaje se serializa sin `NaN`
- [X] T012 Actualizar `compose.yaml` y `compose.dev.yaml`: en `producer`, añadir `USGS_CATALOG_URL`, `USGS_TIMEOUT_SECONDS`, `USGS_MAX_ATTEMPTS`, `USGS_USER_AGENT` y `GAP_MARGIN_MINUTES` con sus valores por defecto; en `compose.dev.yaml`, servicio `usgs-stub` bajo el perfil `test` (imagen de pruebas, orden `python -m tests.support.usgs_stub --port 8080`, misma red, sin puertos publicados). Validar con `docker compose config --quiet` y `docker compose -f compose.yaml -f compose.dev.yaml config --quiet`, y comprobar que `docker compose config --services` sigue listando cinco servicios
- [X] T013 Ejecutar `pytest tests/unit tests/db -q` en el contenedor `tests` y corregir hasta que todo pase, incluidas las pruebas de la spec 002

**Checkpoint**: las piezas comunes están probadas; el feed y la carga pueden avanzar por separado

---

## Phase 3: User Story 1 - Feed en vivo con procedencia completa (Priority: P1) 🎯 MVP

**Goal**: cada consulta al feed queda registrada, su original se guarda una vez por contenido,
las exclusiones se conservan y solo se publican versiones nuevas

**Independent Test**: V1, V2 y V11 de [quickstart.md](quickstart.md)

### Tests for User Story 1

> Escribir primero y comprobar que FALLAN antes de implementar

- [X] T014 [US1] Crear `tests/db/test_feed_cycle.py` con la fuente simulada, un productor de Kafka simulado y `observatory_test`: (a) una respuesta con un terremoto, una voladura (`quarry blast`) y un elemento sin `id` deja una extracción `ok` con `record_count` 3, `earthquake_count` 1, `excluded_count` 2, `published_count` 1, `source_generated_at` igual a `metadata.generated` y `error_detail` que menciona el elemento no identificable y su posición; 1 fila en `excluded_event` con `event_type`, `reason_code` y `extraction_id`; 1 original en `raw_payload` cuyo cuerpo descomprimido es la respuesta recibida; (b) un segundo ciclo con los mismos eventos y otro `metadata.generated` deja 2 extracciones, 1 original con `last_seen_at` posterior, 0 publicados y la exclusión sin duplicar; (c) un 304 deja una extracción `not_modified` con la huella anterior y sin recuentos, y actualiza `last_seen_at`; el segundo ciclo envió `If-Modified-Since`; (d) una revisión con `updated` posterior publica 1; (e) un evento que desaparece de la respuesta sigue en `publish_state` y no se borra nada; (f) si el productor de Kafka simulado falla, `published_count` refleja lo confirmado y el ciclo siguiente publica lo pendiente; (g) `last_successful_feed_request` devuelve el `requested_at` del último ciclo `ok` o `not_modified`; (h) respuesta con cero elementos es `ok` con recuentos a cero; (i) un evento que en una versión es `earthquake` y en la siguiente `quarry blast` (y al revés): cada versión se trata según su tipo, la excluida queda en `excluded_event`, la de terremoto se publica y nada de lo ya guardado se borra; (j) con un reloj inyectado, dos ciclos consecutivos nunca empiezan con menos separación que `PRODUCER_INTERVAL_SECONDS`, aunque el ciclo anterior terminara antes o fallara (FR-007, SC-009); (k) si la base falla al registrar una respuesta ya recibida, el resultado queda pendiente, la fuente no se vuelve a consultar mientras tanto y, cuando la base vuelve, se registra una sola extracción con el `requested_at` original y se publica lo pendiente (FR-001a)

### Implementation for User Story 1

- [X] T015 [US1] Rehacer el ciclo en `producer/app/main.py`: función `feed_cycle(config, producer, pool, state)` que (1) llama a `usgs.fetch_async` con `If-Modified-Since` del estado en memoria; (2) según el resultado: con `ok`, calcula la huella de `features`, clasifica, y en una transacción registra la extracción, guarda el original y las exclusiones; con `not_modified`, registra la extracción con la huella anterior y llama a `touch_payload`; con `invalid_json` o `invalid_structure`, registra la extracción y guarda los bytes recibidos con su huella; con `http_error` o `timeout`, registra solo la extracción; si el registro falla porque la base no está disponible, conserva el resultado en el estado en memoria como pendiente, reintenta registrarlo con la espera de `common/retry.py` y no vuelve a llamar a la fuente hasta conseguirlo (FR-001a); (3) con `ok`, publica en `earthquakes.live` con `publisher.publish_versions` y actualiza `published_count`; (4) devuelve el resultado. El bucle `run` conserva la creación de topics, el pool y los reintentos de `common/` para Kafka y PostgreSQL, espera `PRODUCER_INTERVAL_SECONDS` entre inicios de ciclo, calculado con una función pura `seconds_until_next_cycle(last_start, now, interval, retry_after_until)` que se pueda probar con un reloj inyectado, sin consultar la fuente con más frecuencia, respeta `retry_after_seconds` no volviendo a consultar antes de ese plazo, y actualiza el latido tras cada ciclo registrado, también si la fuente falló (research R12)
- [X] T016 [US1] Eliminar con `git rm` `producer/app/feed.py` y `tests/unit/test_feed.py`; comprobar con una búsqueda que ningún módulo los importa
- [X] T017 [US1] Ejecutar `pytest tests/db/test_feed_cycle.py tests/unit -v` hasta que pase; después `docker compose up -d --build --wait` y comprobar con `docker compose ps` que los cinco servicios están sanos y que `docker compose logs --tail 20 producer` muestra ciclos registrados
- [X] T018 [US1] Validar V11 (clave y campos del mensaje con `kafka-console-consumer`) y repetir el escenario V8 de la spec 002 (reiniciar con `docker compose down` y `docker compose up -d`: mismo recuento y 0 versiones republicadas); guardar esperado, observado y salida en `docs/evidence/003/feed.md`
- [X] T019 [US1] Dejar el sistema una hora y validar V1 con las cuatro consultas de [quickstart.md](quickstart.md): 60 ± 1 consultas, 0 descuadradas, originales = contenidos distintos, antigüedad de la última ingesta menor de dos minutos; añadir el resultado a `docs/evidence/003/feed.md`. Mientras transcurre la hora se puede avanzar con US2 sin reiniciar el productor

**Checkpoint**: MVP. La ingesta en vivo deja procedencia completa y `last_ingestion` es calculable

---

## Phase 4: User Story 2 - Histórico obligatorio de 2025 (Priority: P1)

**Goal**: cargar 2025 mundial con magnitud ≥ 4 con una orden, sin truncar, reanudable, repetible
y con recuentos comprobables

**Independent Test**: V4, V5 y V6 de [quickstart.md](quickstart.md)

### Tests for User Story 2

- [X] T020 [P] [US2] Crear `tests/unit/test_catalog_plan.py`: `month_intervals(start, end)` divide `[2025-01-01, 2026-01-01)` en 12 meses naturales contiguos y sin solapes, y deja parciales el primero y el último si el periodo no empieza o termina en día 1; `plan_intervals` con una función de recuento simulada deja intacto un intervalo con recuento ≤ máximo, divide en dos mitades uno que lo supera y sigue dividiendo de forma recursiva; la unión de los intervalos resultantes es exactamente el periodo; un intervalo de un segundo que aún supera el máximo lanza un error explícito; los instantes se formatean como `2025-01-01T00:00:00Z`
- [X] T021 [P] [US2] Crear `tests/unit/test_catalog_load_cli.py`: sin argumentos, el periodo es `2025-01-01` a `2026-01-01`, magnitud mínima 4, tipo `earthquake` y propósito `historical_load`; `--purpose gap_recovery` sin `--start` y `--end` termina con código 2, y con ellos usa todas las magnitudes y todos los tipos; fin no posterior al inicio, periodo que termina en el futuro y fecha ilegible terminan con código 2 sin hacer ninguna petición; `--all-magnitudes` y `--all-types` quitan los filtros; el nombre de fichero de un intervalo es `<inicio>_<fin>_<filtro>.geojson` con el formato de [data-model.md](data-model.md) §3
- [X] T022 [US2] Crear `tests/db/test_catalog_load.py` con la fuente simulada, productor de Kafka simulado, `observatory_test` y un directorio temporal de datos: (a) carga de dos meses: una extracción por recuento (`request_params.endpoint = 'count'`, `record_count` = declarado) y una por descarga (`endpoint = 'query'`, `window_start`, `window_end`, parámetros, los cuatro recuentos, `content_sha256`), un fichero por intervalo con el cuerpo sin modificar, una fila `raw_payload` con `encoding = 'file'`, ruta relativa y huella igual a la del fichero, y todas las versiones publicadas en el topic del catálogo con `source = 'usgs_catalog'`; (b) un mes cuyo recuento supera el máximo se subdivide y ninguna petición `/query` usa `limit`; (c) un evento presente en dos intervalos se publica una vez y el resumen cuenta 1 repetido; (d) una descarga que trae menos eventos de los declarados hace fallar el intervalo con código 1 y sin fichero aceptado; (e) segunda ejecución: ningún `/query` nuevo, 0 publicados, mismos recuentos; (f) reanudación: tras un fallo de la fuente en el segundo intervalo (código 1), una nueva ejecución descarga solo lo pendiente y termina con código 0; (g) fichero alterado en disco se vuelve a descargar; (h) `--refresh` vuelve a descargar; (i) `--dry-run` no escribe ficheros, extracciones de descarga ni mensajes; (j) total recibido distinto del declarado al terminar da código 3 y el resumen muestra la diferencia; (k) un elemento de otro tipo se guarda como exclusión; (l) el resumen JSON `summary-*.json` contiene intervalos, repetidos, eventos distintos, declarados y diferencia; (m) un 503 persistente de la fuente en un recuento o en una descarga deja una extracción `http_error` con sus intentos y `error_detail`, además del código 1 (FR-001); (n) una descarga con cuerpo ilegible deja una extracción `invalid_json`, el cuerpo guardado en `raw_payload` con la huella de sus bytes, ningún fichero aceptado y código 1 (FR-006); (o) un evento cuya versión del catálogo es igual o anterior a la ya registrada en `publish_state` no se publica y su intervalo cuenta 0 publicados para él; (p) dos cargas lanzadas a la vez con `asyncio.gather` sobre el mismo periodo terminan ambas con código 0, cada fichero coincide con su huella, `publish_state` tiene una fila por evento con su versión más reciente y el conjunto de versiones distintas publicadas es el esperado, aunque algún mensaje se haya enviado dos veces

### Implementation for User Story 2

- [X] T023 [US2] Crear `producer/app/catalog.py` hasta que T020 pase: `month_intervals`, `plan_intervals(interval, count, max_allowed)` con subdivisión recursiva por mitades, `count_events(settings, interval, filters)` y `query_events(settings, interval, filters)` sobre `usgs.fetch_async` (`format=geojson`, `orderby=time-asc`, sin `limit`), detección del 400 por exceso (`exceeds search limit`) como señal para volver a subdividir, y construcción de `request_params` y del nombre de fichero
- [X] T024 [US2] Crear `producer/app/catalog_load.py` hasta que T021 y T022 pasen, con la interfaz de [contracts/catalog-loader.md](contracts/catalog-loader.md): análisis y validación de argumentos (código 2); por cada intervalo, recuento registrado, descarga comprobando que se recibe exactamente lo declarado, escritura del fichero en `DATA_DIR/usgs/catalog/` de forma atómica (fichero temporal y renombrado), `provenance.store_file`, registro de cada petición fallida o ilegible con `provenance.record_extraction` (y `store_body` para la ilegible) antes de terminar con código 1, clasificación, exclusiones, publicación con `publisher.publish_versions` en `earthquakes.catalog` y `published_count`; reutilización de un intervalo cuando existe una extracción `ok` con los mismos parámetros e intervalo cuyo fichero está en disco con la misma huella; deduplicación por `event_id` durante la ejecución; recuento final del periodo; resumen en la salida estándar y en `summary-<fecha>.json`; códigos de salida 0, 1, 2 y 3; `--refresh` y `--dry-run`; creación de topics y reintentos de conexión con `common/`
- [X] T025 [US2] Añadir a `compose.yaml` el servicio `catalog-loader` según [contracts/runtime.md](contracts/runtime.md): perfil `tools`, misma construcción que `producer`, `entrypoint: ["python", "-m", "app.catalog_load"]`, `user: "${LOADER_UID:-0}:${LOADER_GID:-0}"`, `./data:/data` con escritura, variables de base de datos, Kafka y USGS, dependencia de `kafka` y `postgres` sanos, sin puertos y `restart: "no"`. Comprobar que `docker compose config --services` sigue listando cinco servicios y que `docker compose run --rm catalog-loader --dry-run --start 2025-01-01 --end 2025-03-01` muestra dos intervalos con sus recuentos sin descargar nada
- [X] T026 [US2] Eliminar con `git rm` `producer/app/history.py` y adaptar `tests/unit/test_history.py` para que conserve solo las pruebas de `producer/app/replay.py` (`read_replay_events`), escribiendo en la propia prueba las líneas JSON que antes generaba `write_jsonl`; comprobar que nada más importa `history`
- [X] T027 [US2] Validar V6 (`--dry-run --all-magnitudes --all-types --start 2026-09-01 --end 2026-11-01`: los meses con más de 20.000 eventos aparecen subdivididos) y guardar la salida en `docs/evidence/003/catalog-load.md`
- [X] T028 [US2] Ejecutar la carga real de 2025 en dos pasos para probar la reanudación (V5): lanzar `docker compose run --rm catalog-loader`, interrumpirla hacia la mitad, comprobar qué intervalos quedaron completos y volver a lanzarla hasta que termine; anotar el tiempo total. Requiere conexión a Internet y descarga 18.302 eventos de USGS en `data/usgs/catalog/`
- [X] T029 [US2] Validar V4 cuando el consumidor haya procesado todos los mensajes (comprobarlo con `core.message_log`): diferencia 0 frente al total declarado; recuento en `core.event_current` de 2025 con magnitud ≥ 4 igual a «eventos distintos», o diferencia explicada con las filas de cuarentena; procedencia `usgs_catalog`; 0 filas en `replay`; `git status --short data/` sin salida; huella de cada fichero (`sha256sum`) igual a la registrada en `core.raw_payload`; menos de 15 minutos desde que se lanza la orden hasta que termina (SC-006), anotando aparte cuánto tardó después el consumidor en almacenarlo todo. Guardar en `docs/evidence/003/catalog-load.md`
- [X] T030 [US2] Validar la repetición (V5): lanzar la carga otra vez y comprobar que no descarga ningún intervalo, publica 0 y deja iguales los recuentos de `event_current` y `event_version`; añadir a `docs/evidence/003/catalog-load.md`

**Checkpoint**: el histórico obligatorio está en `core`, con recuentos comprobados y ficheros fuera de Git

---

## Phase 5: User Story 3 - La ingesta resiste los fallos de la fuente (Priority: P2)

**Goal**: cada fallo queda registrado, se reintenta con prudencia y no altera lo almacenado

**Independent Test**: V3 de [quickstart.md](quickstart.md)

### Tests for User Story 3

- [X] T031 [US3] Crear `tests/db/test_feed_failures.py` con la fuente simulada y `observatory_test`, partiendo de un ciclo correcto previo: para cada caso (429 con `Retry-After`, 503 en todos los intentos, tiempo agotado, cuerpo no JSON, JSON sin `features`) el ciclo termina sin excepción, deja una extracción con el `outcome`, `http_status`, `attempt_count` y `error_detail` esperados y recuentos nulos, no publica nada, no cambia `publish_state`, `event`-tablas ni exclusiones, y `last_successful_feed_request` sigue siendo la del ciclo correcto anterior; el ciclo siguiente con respuesta correcta funciona; las respuestas ilegibles o no válidas dejan su original guardado con la huella de los bytes; un 503 seguido de 200 deja una sola extracción `ok` con `attempt_count` 2; con `Retry-After` de 300 s el ciclo siguiente no consulta la fuente antes de ese plazo (reloj inyectado)

### Implementation for User Story 3

- [X] T032 [US3] Ajustar `producer/app/main.py` y `producer/app/usgs.py` hasta que T031 pase, sin debilitar las pruebas de T006 ni T014
- [X] T033 [US3] Validar V3 con el sistema real: levantar `usgs-stub` con el perfil `test`, parar el `producer` normal y arrancar uno con `USGS_FEED_URL` apuntando sucesivamente a `/feed/fail-503`, `/feed/fail-429`, `/feed/timeout`, `/feed/not-json` y `/feed/bad-structure`; comprobar las extracciones registradas, que el contenedor sigue `healthy` mientras la fuente falla y que al volver a la fuente real el ciclo siguiente es correcto; restaurar el `producer` normal y guardar en `docs/evidence/003/source-failures.md`

**Checkpoint**: un fallo de USGS es visible en el registro y no detiene ni daña el sistema

---

## Phase 6: User Story 4 - Recuperación de huecos tras una parada larga (Priority: P2)

**Goal**: detectar el periodo que el feed no cubre, avisar con la orden exacta y recuperarlo con
la carga del catálogo

**Independent Test**: V8 de [quickstart.md](quickstart.md)

### Tests for User Story 4

- [X] T034 [P] [US4] Crear `tests/unit/test_gaps.py`: `find_gaps(successful_requests, now, margin)` no devuelve nada con consultas separadas menos de 24 horas, ni con una lista vacía; dos consultas separadas 36 horas dan un hueco `[anterior − margen, siguiente − 24 h + margen)`; una última consulta de hace 36 horas da un hueco abierto que termina en `ahora − 24 h + margen`; `is_covered(gap, recovery_windows)` es cierto cuando la unión de las ventanas lo contiene, también con ventanas contiguas o solapadas, y falso si queda un tramo sin cubrir; `recovery_command(gap)` produce `docker compose run --rm catalog-loader --purpose gap_recovery --start <inicio> --end <fin>` con instantes en UTC

### Implementation for User Story 4

- [X] T035 [US4] Crear `producer/app/gaps.py` hasta que T034 pase, y añadir la consulta que obtiene de `core.extraction` las consultas correctas al feed consecutivas separadas más de 24 horas (función de ventana `lag` sobre `requested_at` con `source = 'usgs_feed'` y `outcome` en `ok`/`not_modified`) y las ventanas de las descargas `gap_recovery` correctas (`request_params ->> 'endpoint' = 'query'`); añadir a `tests/db/test_provenance_writes.py` un caso con extracciones insertadas que compruebe que un hueco de 36 horas se detecta y que pasa a recuperado tras registrar descargas que lo cubren
- [X] T036 [US4] Añadir al arranque de `producer/app/main.py` el aviso de hueco: antes del primer ciclo, si la última consulta correcta dista más de 24 horas, escribir una línea `WARNING` con el formato exacto de [contracts/catalog-loader.md](contracts/catalog-loader.md) («Ingestion gap detected: …») y continuar con el feed sin lanzar ninguna recuperación; sin consultas previas no hay aviso. Añadir la prueba a `tests/db/test_feed_cycle.py`
- [X] T037 [US4] Añadir a `producer/app/catalog_load.py` la opción `--gaps` (lista cada hueco con su intervalo, si está recuperado y la orden para recuperarlo; no consulta la fuente) y comprobar que `--purpose gap_recovery` registra las extracciones con ese propósito y publica por el topic del catálogo; añadir ambos casos a `tests/db/test_catalog_load.py`
- [ ] T038 [US4] Validar V8 con el sistema real. **Requiere confirmación de la usuaria**: el paso 2 retrasa 36 horas el `requested_at` de las extracciones del feed de la base local para simular la parada. Parar el productor, aplicar la simulación, arrancar, comprobar el aviso en menos de un minuto y que el feed sigue, ejecutar la orden indicada, comprobar con SQL que los eventos del periodo están en `core` sin duplicados y que `--gaps` lo da por recuperado. Indicar en la evidencia que la antigüedad es simulada. Antes de aplicar la simulación, anotar el `extraction_id` máximo afectado; al terminar, restaurar las fechas sumando 36 horas a esas mismas filas (`extraction_id` ≤ el anotado y `source = 'usgs_feed'`) y comprobar que `min` y `max` de `requested_at` vuelven a sus valores originales, para que el perfil de la fuente de T044 y T045 no quede distorsionado; los eventos recuperados y sus extracciones `gap_recovery` son reales y se conservan. Guardar en `docs/evidence/003/gap-recovery.md`

**Checkpoint**: una parada larga deja de producir vacíos silenciosos en la serie

---

## Phase 7: User Story 5 - Los originales no crecen sin límite (Priority: P3)

**Goal**: purgar cada 24 horas los originales del feed fuera de retención

**Independent Test**: V9 de [quickstart.md](quickstart.md)

### Tests for User Story 5

- [X] T039 [US5] Crear `tests/db/test_purge_cycle.py`: con originales del feed de `last_seen_at` de hace 8 y 6 días y una referencia de fichero de hace 400 días, la purga con retención 7 elimina solo el primero y devuelve 1; las extracciones siguen todas, con su huella; la función que decide si toca purgar devuelve cierto al arrancar y cuando han pasado 24 horas desde la última, y falso antes (reloj inyectado); la purga registra en el log cuántos eliminó

### Implementation for User Story 5

- [X] T040 [US5] Añadir a `producer/app/main.py` la purga periódica: llamar a `core.purge_raw_payload(RAW_PAYLOAD_RETENTION_DAYS)` al arrancar y cada 24 horas entre ciclos, registrar en el log el número eliminado, y que un fallo de la purga no interrumpa el feed; hasta que T039 pase
- [X] T041 [US5] Validar V9: ejecutar `pytest tests/db/test_purge_cycle.py -v`, reconstruir el productor, comprobar en su log la línea de la purga del arranque y ejecutar la consulta de V9 (0 cuerpos sin observar desde hace más de 8 días); copiar en la evidencia esa línea del log con el número eliminado (constancia que acepta FR-033) y anotar el número y el tamaño real de los originales almacenados (`sum(byte_size)` y `pg_total_relation_size('core.raw_payload')`); guardar en `docs/evidence/003/retention.md`

**Checkpoint**: la retención de 7 días se aplica y está medida

---

## Phase 8: User Story 6 - Ampliar el histórico con 2026 (Priority: P3)

**Goal**: cargar 2026 hasta la fecha con el mismo procedimiento y filtro

**Independent Test**: V7 de [quickstart.md](quickstart.md)

- [X] T042 [US6] Anotar el recuento de 2025 en `core.event_current` y ejecutar `docker compose run --rm catalog-loader --start 2026-01-01 --end <fecha de hoy en UTC>`; requiere conexión a Internet y descarga unos 14.200 eventos
- [X] T043 [US6] Validar V7 cuando el consumidor termine: diferencia 0 con el total declarado; el recuento de 2025 no ha cambiado; ningún `event_id` duplicado; los eventos recientes que también trae el feed conservan su versión más reciente; y una consulta sobre `core.extraction` muestra por separado la carga de 2025 y la de 2026 con su periodo, filtro y fecha de extracción. Guardar en `docs/evidence/003/catalog-load-2026.md`

**Checkpoint**: el espacio real contiene 2025 y 2026 con magnitud ≥ 4 además del feed

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T044 Crear `tests/analysis/source_profile.py` (research R14): lee los cuerpos del feed guardados en `core.raw_payload`, los ficheros de `data/usgs/catalog/` y `core.extraction`, y escribe `docs/evidence/003/source-profile.md` con, por cada campo de `properties` y de `geometry`, tipos observados, porcentaje de nulos y mínimo y máximo; tipos de evento y de geometría; frecuencia real de cambio del feed (contenidos distintos por hora); resultados de las consultas por tipo; latencia (`duration_ms`: mediana, percentil 95 y máximo); y retraso de publicación (`updated − time` e `first_ingested_at − event_time`: mediana y percentil 95). Indica cuántas respuestas y eventos se analizaron y en qué periodo
- [ ] T045 Ejecutar V10 (`python -m tests.analysis.source_profile` en el contenedor `tests`) con al menos una hora de feed y la carga de 2025 disponibles, y revisar que el 100 % de los campos utilizados del feed y del catálogo aparece con tipo y porcentaje de ausencias (SC-013)
- [ ] T046 Ampliar `docs/report.md` con un apartado «Fuentes y extracción»: descripción de la respuesta del feed y del catálogo a partir de `source-profile.md` (estructura, tipo, unidad y significado de cada campo usado, campos opcionales y con qué frecuencia faltan, frecuencia de actualización, errores y latencia observados); registro de procedencia en tabla (feed, histórico de 2025 y ampliación de 2026: fuente, periodo, filtros, fecha de extracción, consultas y número de registros), indicando qué periodos tienen todas las magnitudes y cuáles solo magnitud ≥ 4; huella y retención de originales con el tamaño medido; comportamiento ante fallos de la fuente; recuperación de huecos y su limitación (el catálogo se consulta como está en ese momento); la limitación de alcance sobre eventos eliminados, fusionados o revisados por USGS cuando ya están fuera del feed (enunciado §5), que el histórico es una instantánea del catálogo en la fecha de extracción (enunciado §4.2), y el único caso en que una consulta puede quedar sin registro (reinicio del productor con un resultado pendiente de registrar, research R4)
- [X] T047 Actualizar el diccionario de datos de `docs/report.md` con los dos usos de [data-model.md](data-model.md) §8 (`extraction.error_detail` para elementos no identificables y `request_params.endpoint`) y los valores reales de `source`, `purpose` y `reason_code`; ejecutar `pytest tests/db/test_data_dictionary.py` y comprobar que sigue pasando
- [X] T048 [P] Ampliar `README.md`: carga del histórico de 2025 con una orden, ampliación a 2026, cómo interpretar el resumen y los códigos de salida, qué hacer ante el aviso de hueco y `--gaps`, dónde quedan los ficheros (`data/usgs/catalog/`) y cómo regenerarlos, `LOADER_UID` y `LOADER_GID` en Linux, las variables nuevas y la nueva semántica de salud del productor (sigue sano aunque USGS falle; se ve en la antigüedad de la última ingesta); órdenes en `bash`. Actualizar en `db/seeds/README.md` la referencia al procedimiento de descarga, y en `specs/002-platform-data-model/contracts/runtime.md` la frase del latido del productor («tras cada ciclo correcto» pasa a «tras cada ciclo registrado, también si la fuente falla»), con una nota que remita a [contracts/runtime.md](contracts/runtime.md) de esta spec (research R12)
- [X] T049 Validar V12: ejecutar `pytest tests/db tests/unit tests/contract -v` y guardar la salida en `docs/evidence/003/tests.txt`; comprobar con `git diff 002-platform-data-model --stat -- db/sql consumer api frontend producer/app/replay.py` que no hay cambios fuera del alcance, o justificarlos por escrito en `plan.md`
- [ ] T050 Comprobar en el equipo Linux que `docker compose run --rm catalog-loader --dry-run` y una descarga pequeña escriben en `./data` con el usuario propio usando `LOADER_UID=$(id -u)` y `LOADER_GID=$(id -g)`, y corregir `compose.yaml` o el README si falla (research R9). Si no hay acceso a ese equipo, dejar la tarea sin marcar y anotarlo en la evidencia
- [ ] T051 Completar `docs/evidence/003/README.md` con la tabla de V1 a V12 (escenario, esperado, observado, resultado y enlace), sin marcar ninguno como superado sin haberlo ejecutado; ejecutar `bash .claude/skills/verify-stack/scripts/scan-evidence.sh docs/evidence/003`
- [ ] T052 Revisar el cumplimiento de la constitución v2.1.0 (principios I, II, III, V, VI, IX e idioma) y anotarlo en `docs/evidence/003/README.md`, indicando que la desviación del principio V queda cerrada y cuáles siguen abiertas (III en la spec 004, VIII en la 006); confirmar que `git status` no muestra ficheros de `data/`, `.env` ni credenciales antes de cualquier commit

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias
- **Foundational (Phase 2)**: depende de Setup; bloquea todas las historias
- **US1 (Phase 3)**: depende de Foundational
- **US2 (Phase 4)**: depende de Foundational; independiente de US1
- **US3 (Phase 5)**: depende de US1 (prueba el ciclo del feed ante fallos)
- **US4 (Phase 6)**: depende de US1 (aviso al arrancar) y de US2 (la recuperación es la carga)
- **US5 (Phase 7)**: depende de US1
- **US6 (Phase 8)**: depende de US2
- **Polish (Phase 9)**: depende de todas

```text
Setup → Foundational ─┬→ US1 ─┬→ US3 ─────────┐
                      │       ├→ US5 ─────────┤
                      │       └→ US4 ←┐       ├→ Polish
                      └→ US2 ─────────┴→ US6 ─┘
```

### Within Each User Story

- Las pruebas se escriben y fallan antes de implementar
- `producer/app/main.py`: T015 (US1), T032 (US3), T036 (US4) y T040 (US5), en ese orden
- `producer/app/catalog_load.py`: T024 (US2) y T037 (US4)
- `compose.yaml`: T012 y T025
- `tests/db/test_feed_cycle.py`: T014 y T036; `tests/db/test_catalog_load.py`: T022 y T037
- T019 (una hora de feed) puede transcurrir mientras se trabaja en US2, sin reiniciar el productor
- T045 necesita T019 y T029 terminadas

### Parallel Opportunities

- Setup: T002 junto a T001
- Foundational: T008 y T009 entre sí y con T006 y T007
- US2: T020 y T021
- US1 y US2 pueden avanzar a la vez tras la fase 2 (ficheros distintos, salvo `compose.yaml`)
- Polish: T048 junto a T046

---

## Parallel Example: Foundational

```bash
# Módulos sin dependencias entre sí, en paralelo:
Task: "Crear producer/app/fingerprint.py y tests/unit/test_fingerprint.py"
Task: "Crear producer/app/classify.py y tests/unit/test_classify.py"
Task: "Crear producer/app/usgs.py hasta que tests/unit/test_usgs_client.py pase"
```

## Parallel Example: User Story 2

```bash
# Pruebas unitarias de la carga, en paralelo:
Task: "Crear tests/unit/test_catalog_plan.py"
Task: "Crear tests/unit/test_catalog_load_cli.py"
```

---

## Implementation Strategy

### MVP First (US1)

1. Setup y Foundational
2. US1: el feed registra cada consulta, guarda originales y exclusiones
3. **Parar y validar**: V1, V2 y V11; `last_ingestion` calculable

### Incremental Delivery

1. MVP (US1)
2. US2: histórico de 2025 cargado y comprobado
3. US3: fallos de la fuente probados
4. US4: huecos detectados y recuperables
5. US5: retención aplicada
6. US6: 2026 cargado
7. Polish: perfil de la fuente, memoria, README y evidencias

### Reglas de integración

- El trabajo se hace en la rama `003-usgs-ingestion`, creada desde `002-platform-data-model`.
  No se fusiona en `main` mientras sigan abiertas las desviaciones de los principios III
  (spec 004) y VIII (spec 006)
- Commit tras cada tarea o grupo lógico, con mensaje en inglés
- T028 y T042 descargan datos reales de USGS: comprobar antes que hay conexión y espacio
- T038 modifica marcas de tiempo de la base local y las restaura al terminar: no ejecutarla sin confirmación, y no dar la tarea por cerrada sin haber comprobado la restauración
- Ninguna tarea necesita `docker compose down -v`; si hiciera falta, pedir confirmación

## Notes

- Las cifras de USGS de [research.md](research.md) (18.302 eventos en 2025, 14.218 en 2026) son
  del 2026-11-15; el catálogo sigue vivo y pueden variar. La comprobación es siempre contra el
  recuento declarado en el momento de la carga
- Hasta la spec 004 el consumidor envía a cuarentena los eventos sin magnitud: en la
  recuperación de un hueco (todas las magnitudes) puede haber diferencia entre publicados y
  almacenados; se explica con las filas de cuarentena, no se corrige aquí
- La carga publica 18.302 mensajes de golpe: esperar a que el consumidor termine antes de
  contar (comparar `core.publish_state` con `core.message_log`)
- T050 depende del equipo Linux; como T057 de la spec 002, puede quedar pendiente sin bloquear
  el resto
