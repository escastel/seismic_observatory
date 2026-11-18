---

description: "Task list for feature 006: query API conforming to the contract"
---

# Tasks: API de consulta conforme al contrato

**Input**: [plan.md](plan.md), `spec.md`, [research.md](research.md),
[data-model.md](data-model.md), [contracts/api.md](contracts/api.md),
[quickstart.md](quickstart.md); contrato normativo
`resources/observatorio-sismico/CONTRATO-API.md`

**Tests**: incluidas (principio IX, FR-031). Pruebas de comportamiento: comprueban respuestas,
códigos HTTP, recuentos y estado de la base; nunca la presencia de texto en el código.

**Reglas**: código, nombres y comentarios en inglés; documentación y textos visibles en español.
Finales de línea LF. Nunca leer ni imprimir `.env`; no ejecutar `docker compose config`. **Sin
cambios de modelo** (ni `db/sql/`, ni tablas, ni índices, ni funciones; solo con necesidad
demostrada y justificada por escrito, plan R9). Sin dependencias nuevas. Nada de datos en Git.
**Nunca dos ejecuciones de `tests/db` o `tests/query_api` a la vez** (comparten `observatory_test`).
`docker compose down -v` pide confirmación explícita.

**Agentes** (etiqueta `[A#]`, norma «Orquestación de agentes» de `CLAUDE.md`):

- `[A0]` sesión principal: `main.py`, `db.py`, `filters.py`, `queries.py`, `stats.py` (SQL),
  Docker y base local, memoria, evidencias e integración final.
- `[A1]` agente nuevo en segundo plano, **Sonnet**: código puro y pruebas.
- `[A2]` agente nuevo en segundo plano, **Haiku**: documentación y tareas mecánicas.

Cada agente recibe un prompt corto que apunta a este fichero y a los contratos (nunca `fork`),
solo toca los ficheros listados en su tarea y ejecuta **solo sus pruebas de `tests/unit` y
`tests/contract`**. Las pruebas que usan la base (`tests/db`, `tests/query_api`) y la suite completa las
ejecuta `[A0]` una vez por fase. Los agentes no hacen commit, no tocan `.env`, no ejecutan
`down -v` y informan en menos de 200 palabras. `[P]` = paralelizable con otras tareas `[P]` de la
misma fase porque sus ficheros no se solapan. `main.py` y `queries.py` los edita solo `[A0]`, en
orden.

## Format: `[ID] [P?] [Story] [Agente] Description`

---

## Phase 1: Preparación (bloquea todo)

- [X] T001 [A0] Comprobar contra el esquema real que `core.quarantine` y `replay.quarantine` tienen las columnas `reason_codes` (arreglo de texto) e `is_synthetic` y que `quality_flags` es `text[]` en `event_current` (`db/sql/040_event_tables.sql`, `db/sql/041_consumer_quality.sql`); anotar el resultado en `docs/evidence/006/00-environment.md` (equipo, SO, versión de Docker, volumen de datos de `core` y `replay`). Si falta alguna, parar y revisar R5 del plan.
- [X] T002 [A0] Añadir `max_features` a `ApiSettings` en `common/settings.py` (variable opcional `API_MAX_FEATURES`, por defecto 1000, entero entre 1 y 10000, error de configuración claro si no es válido) y pasarla en `compose.yaml` al servicio `api` como `API_MAX_FEATURES: ${API_MAX_FEATURES:-1000}`; ampliar `tests/unit/test_common_settings.py` con valor por defecto, valor válido y valor inválido.

**Checkpoint**: `pytest tests/unit/test_common_settings.py` en verde.

---

## Phase 2: Fundamentos compartidos (bloquea todas las historias)

- [X] T003 [A0] Reescribir `api/app/db.py` con dos pools de solo lectura abiertos en segundo plano con reintento: `live` (`search_path = core`) y `replay` (`search_path = replay, core`), `command_timeout=10`, `max_size` 10 el real y 5 el de reproducción; `app.state.pools` con `None` hasta abrirse; función `pool_for(request, mode)` que lanza el error de base no disponible si el pool pedido no existe; mantener `stop` cancelando ambas tareas y cerrando ambos pools. Un fallo del pool `replay` no debe afectar al `live`.
- [X] T004 [A0] Crear `api/app/filters.py`: modelo `QueryFilters` (`mode` en `live|replay` por defecto `live`; `start` y `end` ISO 8601 **con zona**, sin zona se rechaza; `min_mag` número finito; `country_id` 1 a 8 alfanuméricos; `exclude_synthetic` booleano), la regla `start` < `end` (iguales también se rechazan) y la función única `build_where(filters, now)` que devuelve `(sql, valores)` según la tabla «Filtro común» de `data-model.md`: ventana por defecto `event_time >= now - 24 h` solo en `live` sin `start`; `end` exclusivo; la magnitud nula no cumple `min_mag`; en `live`, condición de sintético `NOT starts_with(event_id,'synthetic-') AND NOT ('synthetic' = ANY(quality_flags))`; en `replay`, esa misma condición solo si `exclude_synthetic`. El valor de `now` entra por parámetro (una sola evaluación por petición) y se devuelve el periodo efectivo.
- [X] T005 [P] [A1] Crear `api/app/serialize.py`: `to_ms(dt)` con `(dt - epoch) // timedelta(milliseconds=1)` (entero exacto, válido antes de 1970 en Windows y Linux); `finite_or_none(x)` que convierte NaN, infinito y ausente en `None`; `feature_from_row(row, replay: bool)` que produce la `Feature` de `data-model.md` (coordenadas `[lon, lat, depth]`, propiedades `mag`, `magType`, `place`, `time`, `updated`, `country_id`, `country_name`, `continent`, `subregion` y, solo en `replay`, `replayed_at` y `synthetic`); `JsonResponse` que renderiza con `allow_nan=False`. Pruebas en `tests/unit/test_api_serialize.py`: instante anterior a 1970, magnitud y profundidad nulas, NaN e infinito a `null`, orden de coordenadas, `synthetic` por prefijo y por marca, ausencia de `replayed_at` en modo real.
- [X] T006 [P] [A1] Crear `tests/unit/test_api_filters.py` (sobre `api/app/filters.py` de T004, sin base): `start` sin zona → error; `start` ≥ `end` → error; `min_mag` NaN, infinito y texto → error; `country_id` vacío o con símbolos → error; `mode` desconocido → error; ventana de 24 horas solo en `live` sin `start`, nunca en `replay`; con el mismo `now`, mapa y estadísticas obtienen el mismo `where` y los mismos valores; en `live` el filtro de sintéticos va siempre y `exclude_synthetic` no lo quita ni lo añade; en `replay` solo con `exclude_synthetic`; los valores nunca se interpolan en el texto SQL.
- [X] T007 [A0] Manejadores globales en `api/app/main.py` (plan R4): fallos de base (`OSError`, `asyncpg.PostgresError`, `asyncpg.InterfaceError`, `TimeoutError`) y pool inexistente → 503 `{"error":"database_unavailable","detail":...}`; `RequestValidationError` → 422 `{"error":"invalid_parameters","detail":[{"param":...,"message":...}]}`; error inesperado → 500 `{"error":"internal_error",...}` con registro en log y sin trazas en el cuerpo. Todos con `JsonResponse`.
- [X] T008 [A1] Crear `tests/query_api/__init__.py` y `tests/query_api/conftest.py`: fixture de sesión que reutiliza la base `observatory_test` de `tests/db/conftest.py`, monta la aplicación real (`api.app.main`) con ambos pools apuntando a esa base (sustituyendo `db.start`), expone un cliente HTTP asíncrono (ASGI) y helpers para insertar eventos con las funciones del modelo (`apply_event_version`) en `core` o en `replay` y para vaciar entre pruebas sin tocar `dim_country` ni `dim_date`. Incluir un helper `stop_database()`/`start_database()` que cierra los pools de la aplicación para simular la base caída sin detener el contenedor.

**Checkpoint**: `pytest tests/unit/test_api_serialize.py tests/unit/test_api_filters.py` en verde; la fixture de `tests/query_api` se importa sin errores.

---

## Phase 3: US1 — Eventos con formato único y conforme al contrato (P1) 🎯 MVP

**Objetivo**: `GET /api/eventos` siempre `FeatureCollection` con `metadata`, filtros y nulos
correctos, una versión por evento, solo datos reales. **Prueba independiente**: pedir eventos sin
parámetros, con cada filtro y combinados, y comprobar estructura contra el contrato.

- [X] T009 [US1] [A0] En `api/app/queries.py` (reescrito): `fetch_page(conn, where, limit, offset)` con `ORDER BY f.event_time DESC, f.event_id ASC` y `LEFT JOIN dim_country`; `count_total(conn, where)`; `count_null_magnitude(conn, where_sin_min_mag)` (eventos con magnitud nula que cumplen el resto de filtros); `quarantine_counts(conn)` con la consulta de `data-model.md` (`total` e `invalid_geometry`, solo `NOT is_synthetic`); `last_ingestion(pool)` con la consulta de `data-model.md` sobre `core.extraction` (`source = 'usgs_feed' AND outcome IN ('ok','not_modified')`, siempre con el pool real). Todo con parámetros enlazados. Retirar las funciones heredadas (`country_stats`, `timeline_stats`, etc.) se hace en T034.
- [X] T010 [US1] [A0] Ruta `GET {prefix}/eventos` en `api/app/main.py`: dependencia de parámetros (`QueryFilters` + `limit` entre 1 y `max_features`, por defecto `max_features`; `offset` ≥ 0); una transacción `REPEATABLE READ` de solo lectura con página, total, nulos y cuarentena; respuesta con `metadata` (`generated`, `last_ingestion`, `mode`, `count`, `total`, `truncated = offset + count < total`, `limit`, `offset`, `next_offset`, `null_magnitude {count, excluded}`, `quarantined {total, invalid_geometry}`); sin resultados → 200 con `features: []`. Sin parámetro `format` ni respuesta alternativa.
- [X] T011 [P] [US1] [A1] `tests/query_api/test_events_contract.py` (comportamiento, base real): estructura completa de `metadata`; sin eventos → 200 y `features: []`; coordenadas `[lon, lat, prof]`; tiempos enteros; magnitud, profundidad y país `null` y nunca NaN; un evento con tres versiones aparece una vez con la vigente; ventana por defecto de 24 h (evento de hace 23 h entra, de hace 25 h no); `start` inclusivo y `end` exclusivo con eventos exactamente en cada instante; `min_mag` con evento de magnitud exactamente igual; `country_id`; combinación de los tres; magnitud nula con `min_mag` (fuera y contada con `excluded: true`) y sin él (`mag: null`, `excluded: false`); un sintético insertado en `core` no aparece en modo real; evento marítimo con `country_id: null` aparece sin filtro de país y no con él.
- [X] T012 [P] [US1] [A1] `tests/query_api/test_events_ingestion_flow.py` (comportamiento): evento nuevo visible tras escribirlo con las funciones del modelo; el mismo mensaje repetido no cambia `total`; revisión posterior cambia `mag`, `updated` y el país si cambia; versión antigua tardía no cambia nada; un mensaje con coordenadas inválidas (usando los mensajes de `tests/synthetic/cases.py` y el consumidor real si la fixture lo permite, o su función de evaluación y escritura en cuarentena) no genera ningún `Feature` y `quarantined.invalid_geometry` aumenta en 1.
- [X] T013 [US1] [A0] Ejecutar `tests/query_api/test_events_contract.py` y `tests/query_api/test_events_ingestion_flow.py` (una sola ejecución de `tests/query_api`) y corregir lo que falle en el código; no se relajan las pruebas.

**Checkpoint**: US1 verde; con el stack levantado, `GET /api/eventos` responde conforme al contrato.

---

## Phase 4: US2 — Reproducción identificada y aislada de lo real (P1)

**Objetivo**: `mode=replay` lee solo el esquema `replay` con etiqueta «REPRODUCCIÓN»; lo real no
cambia. **Prueba independiente**: conteos reales antes y después de una reproducción, y consulta
en modo reproducción.

- [X] T014 [US2] [A0] Extender la ruta de eventos de `api/app/main.py` para `mode=replay`: pool `replay`, sin ventana de 24 h, `metadata.label = "REPRODUCCIÓN"`, `metadata.last_replayed_at` (`max(replayed_at)` o `null`), `replayed_at` y `synthetic` en cada `Feature`, `last_ingestion` siempre del esquema real y `exclude_synthetic`; la `mode` desconocida ya la rechaza `QueryFilters` con 422.
- [X] T015 [P] [US2] [A1] `tests/query_api/test_replay_mode.py` (comportamiento): en modo `replay` se devuelven solo eventos de `replay` y con `replayed_at`; sin filtros de tiempo salen eventos de 2025 (sin ventana de 24 h); `start`, `end`, `min_mag`, `country_id` y la paginación siguen aplicándose; `metadata.mode == "replay"` y `label == "REPRODUCCIÓN"` en toda respuesta de reproducción, también con 0 eventos; `last_ingestion` es la del esquema real (insertar una extracción `ok` en `core.extraction`) y `last_replayed_at` el máximo de `replayed_at`; el mismo `event_id` en ambos esquemas con valores distintos se devuelve con los propios en cada modo; sintéticos (`synthetic-…`) presentes con `synthetic: true` y ausentes con `exclude_synthetic=true`; `mode=otro` → 422; sin `mode` = real.
- [X] T016 [P] [US2] [A1] `tests/query_api/test_replay_isolation.py` (comportamiento): registrar la respuesta completa de modo real (eventos y, cuando exista, estadísticas) con un periodo fijo, insertar varios miles de eventos en `replay` con las funciones del modelo, repetir y comprobar igualdad exacta; un sintético solo en `replay` no aparece en el modo real; vaciar `replay` con `replay.reset()` deja el modo real igual y el modo `replay` con 0 eventos.
- [X] T017 [US2] [A0] Ejecutar `tests/query_api/test_replay_mode.py` y `tests/query_api/test_replay_isolation.py` y corregir el código.

**Checkpoint**: US1 y US2 verdes.

---

## Phase 5: US3 — Salud y errores con la base caída (P1)

**Objetivo**: salud honesta y errores explícitos. **Prueba independiente**: salud con sistema sano
y con la base detenida.

- [X] T018 [US3] [A0] Ruta `GET {prefix}/salud` en `api/app/main.py` (siempre 200): `status` (`ok`/`degraded`), `database` y `replay_database` (`ok`/`unavailable`, comprobados con una consulta ligera por pool), `generated`, `last_ingestion` (consulta de T009; `null` si no hay ninguna extracción correcta o si la base falla). Sin credenciales, host ni versión. Retirar la ruta `/health` y `LAST_INGESTION_SQL` heredados.
- [X] T019 [P] [US3] [A1] `tests/query_api/test_health_and_errors.py` (comportamiento): sistema sano → `ok` con la fecha de la última extracción `ok` del feed; una extracción posterior con `http_error` o `timeout` no mueve `last_ingestion`; una `not_modified` sí; un evento con `ingested_at` reciente y ninguna extracción → `last_ingestion: null` (la última fila escrita no cuenta); con los pools cerrados (`stop_database()`) → salud 200 `degraded`, eventos 503 y estadísticas 503, todos con cuerpo JSON `{"error":"database_unavailable",...}` y nunca `features: []` con 200; tras reabrir, vuelve a `ok`; el cuerpo de salud no contiene contraseña, usuario ni host.
- [X] T020 [US3] [A0] Ejecutar `tests/query_api/test_health_and_errors.py` y corregir; comprobar con el stack real que el healthcheck de Docker del servicio `api` sigue sano.

**Checkpoint**: P1 completo (US1, US2, US3).

---

## Phase 6: US4 — Estadísticas por hora, país y comparación histórica (P2)

**Objetivo**: `GET /api/estadisticas` conforme a `contracts/api.md`. **Prueba independiente**:
comparar cada agregación con el cálculo directo sobre el estado actual, antes y después de una
revisión.

- [X] T021 [US4] [A0] Crear la parte SQL de `api/app/stats.py`: `hourly_counts` con `date_bin('1 hour', event_time, TIMESTAMPTZ '2000-01-01 00:00:00+00')` y `generate_series` entre el inicio y el fin efectivos (fin exclusivo, horas vacías a 0; en `replay` sin `start`, de la primera a la última hora con datos); más de 10.000 ventanas → error de validación 422 que pide acotar; `by_country` con `LEFT JOIN dim_country` y rótulo «Sin país asignado» para `country_id` nulo; `magnitude_distribution` (tramos `floor(magnitude)` de 1 unidad, incluidos negativos, nulas en `unvalued`); `depth_distribution` (`<0`, `0–70`, `70–300`, `≥300` km, nulas en `unvalued`); `total` con el mismo `build_where` de T004.
- [X] T022 [P] [US4] [A1] Crear en `api/app/stats.py` solo la función pura `compare(recent_count, baseline_events, year)` que calcula `days` (365 o 366 según el año), `daily_mean` y `ratio` (`recent_count / daily_mean`, o `"ND"` si la media es 0) y devuelve el `warning` fijo de periodo reciente incompleto; pruebas en `tests/unit/test_api_comparison.py`: año bisiesto, media 0 → `"ND"`, el denominador cuenta los días sin eventos (p. ej. 3 eventos en 365 días da `3/365`, no `3/días con eventos`), el aviso siempre presente. (No toca el SQL de T021: añadir al fichero tras T021 para evitar conflicto.)
- [X] T023 [US4] [A0] Consultas de la comparación en `api/app/stats.py`: recientes = eventos en `[ancla − 24 h, ancla)` y referencia = eventos de `[baseline_year-01-01, baseline_year+1-01-01)` UTC, ambos con `min_mag`, `country_id` y `exclude_synthetic` pero sin `start`/`end`; ancla = `end` si se da o `now` en `live`; en `replay`, `end` o el último `event_time` del espacio de reproducción, con aviso adicional de que la referencia es solo lo reproducido.
- [X] T024 [US4] [A0] Ruta `GET {prefix}/estadisticas` en `api/app/main.py` con los parámetros comunes más `baseline_year` (entero, por defecto 2025; sin `limit` ni `offset`); todas las consultas en una transacción `REPEATABLE READ` de solo lectura; respuesta según `contracts/api.md`: `mode`, `metadata` (con `label` y `last_replayed_at` en `replay`), `scope: "complete"`, `map_truncated` (total mayor que `max_features`), `period`, `filters`, `unit`, `total`, `hourly`, `by_country`, `magnitude_distribution`, `depth_distribution`, `comparison`.
- [X] T025 [P] [US4] [A1] `tests/query_api/test_statistics.py` (comportamiento): `total` igual a `metadata.total` del mapa para una batería de filtros (sin filtros, `start`/`end`, `min_mag`, `country_id`, combinados, en ambos modos); ventana de una hora con un evento a las 10:00:00.000 (entra en 10:00) y otro a las 10:59:59.999 y otro a las 11:00:00.000 (este entra en 11:00); horas vacías con 0; «Sin país asignado» como categoría con su recuento y suma de países = `total`; nulas de magnitud y profundidad en `unvalued` y tramos + `unvalued` = `total`; magnitud negativa conservada en su tramo; comparación con media 0 → `"ND"`; el denominador incluye días vacíos; el aviso presente; una revisión que cambia magnitud o país mueve el evento entre tramos/países y una versión antigua tardía no cambia nada; en `replay`: `label`, `mode`, sin mezcla con `core` y `exclude_synthetic`; selección mayor que `max_features` → `map_truncated: true` y `total` completo (las estadísticas no se calculan sobre la muestra); más de 10.000 ventanas → 422.
- [X] T026 [US4] [A0] Ejecutar `tests/query_api/test_statistics.py` y corregir; comprobar que cada resultado indica periodo, filtros, unidad y registros sin valor.

**Checkpoint**: US4 verde.

---

## Phase 7: US5 — Respuestas acotadas y paginadas (P2)

**Objetivo**: máximo documentado, `truncated`, total y recorrido exacto por páginas.
**Prueba independiente**: recorrer todas las páginas de una selección truncada.

- [X] T027 [P] [US5] [A1] `tests/query_api/test_pagination.py` (comportamiento): con `API_MAX_FEATURES` pequeño (p. ej. 50) y 130 eventos, 1.ª página con `truncated: true`, `total: 130`, `next_offset: 50`; recorrer con `next_offset` hasta `null` y comprobar que cada evento aparece una vez y el orden global es `time` descendente; empates de tiempo a caballo de dos páginas sin pérdidas ni repeticiones; menos eventos que el máximo → `truncated: false` y `total == count`; `limit` mayor que el máximo y `offset` negativo → 422; página más allá del final → 200 con `features: []`, `truncated: false`; igual en modo `replay`.
- [X] T028 [US5] [A0] Ejecutar `tests/query_api/test_pagination.py` y corregir (el máximo se inyecta desde la configuración, no se reescribe el código para la prueba).

**Checkpoint**: US5 verde.

---

## Phase 8: US6 — Acceso controlado y parámetros validados (P2)

**Objetivo**: CORS exacto sin credenciales, superficie mínima, 422 útiles. **Prueba
independiente**: peticiones con orígenes y parámetros distintos.

- [X] T029 [US6] [A0] En `api/app/main.py`: `allow_credentials=False`, `max_age=600`, mantener `allow_methods=["GET","OPTIONS"]` y `allow_headers=["Content-Type","ngrok-skip-browser-warning"]`; desactivar `docs_url` y `redoc_url`; conservar `openapi_url` bajo el prefijo. Comprobar que `uvicorn` se lanza en `0.0.0.0:8000` en `api/Dockerfile` y que `compose.yaml` publica `127.0.0.1:8000:8000` (sin tocar nada si ya es así).
- [X] T030 [P] [US6] [A1] Reescribir `tests/contract/test_api_contract.py` (sin base real; con la aplicación y pools simulados donde haga falta): conjunto exacto de rutas (`/api/eventos`, `/api/estadisticas`, `/api/salud`, `/api/openapi.json`); ninguna ruta acepta `POST`, `PUT`, `PATCH` ni `DELETE` (405); ninguna ruta de administración; el preflight desde el origen permitido y desde `http://localhost:4200` responde con la cabecera de origen exacta, `GET, OPTIONS` y `ngrok-skip-browser-warning`, y **sin** `access-control-allow-credentials`; desde otro origen no hay cabeceras de acceso; 422 con `error`, `param` y mensaje para `mode=x`, `start` sin zona, `start >= end`, `min_mag=abc`, `limit=0`; los parámetros desconocidos (`format=geojson`, `country=Chile`) se ignoran sin error; el módulo de la API no importa ningún cliente de USGS ni de Kafka.
- [X] T031 [US6] [A0] Ejecutar `tests/contract/test_api_contract.py` y corregir; con el stack real, comprobar el preflight con `curl -i -X OPTIONS` desde el origen de `CORS_ORIGINS` (sin imprimir `.env`: leer el origen de la prueba, no del fichero) y desde uno no permitido.

**Checkpoint**: P2 completo (US4, US5, US6).

---

## Phase 9: US7 — Retirar lo heredado fuera del contrato (P3)

**Objetivo**: superficie mínima y documentada. **Prueba independiente**: no queda código ni ruta
heredada y los clientes del contrato siguen funcionando.

- [X] T032 [US7] [A0] Comprobar con `grep` (Grep) el uso de `date_from`, `date_to`, `min_magnitude`, `max_magnitude`, `country=`, `format=`, `/estadisticas/paises`, `/estadisticas/timeline` y `/api/health` en `frontend/src/`, `resources/observatorio-sismico/frontend/src/`, `compose.yaml`, `README.md`, `docs/`, `tests/` y scripts; registrar el resultado en `docs/evidence/006/v14-surface.md` y contrastarlo con la tabla de R8; si aparece un uso no previsto, parar y revisar R8.
- [X] T033 [US7] [A0] Eliminar de `api/app/schemas.py` los modelos heredados que ya nadie usa (`EventFilters`, `EventsResponse`, `CountryStatsResponse`, `TimelineResponse`, `GeoJSONFeatureCollection`, etc.) y dejar solo lo que siga haciendo falta (o borrar el fichero si queda vacío); eliminar de `api/app/queries.py` y `main.py` cualquier función, alias o ruta heredados (`country`, `date_from`, `date_to`, `min_magnitude`, `max_magnitude`, `format`, `/estadisticas/paises`, `/estadisticas/timeline`, `/health`).
- [X] T034 [US7] [A0] Retirar `tests/unit/test_statistics_filters.py` (prueba de funciones eliminadas; su intención —mismo filtro en las agregaciones— la cubre T006 y T025) y las referencias heredadas de `tests/integration/load_test.py` y `tests/integration/test_load_test.py` si usan rutas o parámetros retirados; ejecutar `pytest tests/unit tests/contract` y comprobar que nada importa lo eliminado.
- [X] T035 [P] [US8] [A2] Crear `docs/evidence/006/README.md` (español) con el índice de escenarios V1–V16 de [quickstart.md](quickstart.md): una tabla con id, qué comprueba, fichero de evidencia previsto (los de T037 a T040) y estado «pendiente»; `[A0]` actualiza el estado al guardar cada evidencia. Fichero exclusivo de esta tarea.

**Checkpoint**: la API solo ofrece lo del contrato; el contrato sigue verde.

---

## Phase 10: US8 — Evidencia, rendimiento y documentación (P3)

**Objetivo**: evidencia ejecutada con el sistema real. **Prueba independiente**: seguir el README
y revisar `docs/evidence/006/`.

- [X] T036 [P] [US8] [A1] Crear `tests/benchmark/api_latency.py`: tres tamaños de resultado (página de ~10 eventos con filtro estrecho, página de 1.000 y estadísticas de un año de datos de 2025), 5 peticiones de calentamiento y 30 medidas secuenciales por tamaño, mediana, p95 y máximo; imprime equipo (CPU, RAM, SO), versión de Docker, volumen de datos y esquema usado; sale con código ≠ 0 si la mediana supera 2 s (SC-008); si `core` no tiene 2025, usa `mode=replay` e indica que la medición es sobre el espacio de reproducción. Solo lee por HTTP; no escribe en la base.
- [X] T037 [A0] Levantar el stack con `docker compose up --build -d` (skill `verify-stack`), asegurar datos de 2025 en `core` (spec 003) y la selección de la spec 005 para `replay`, y ejecutar V1–V8 y V11 del [quickstart](quickstart.md); guardar en `docs/evidence/006/` un `.md` con esperado/observado por escenario y su salida (`v1-contract.md`, `v2-filters.md`, `v3-new-and-repeat.md`, `v4-revision-and-stale.md`, `v5-null-magnitude.md`, `v6-geometry.md`, `v7-no-country.md`, `v8-truncation.md`, `v11-statistics.md`). Los casos que necesitan mensajes concretos (V3 a V7) usan los sintéticos de `tests/synthetic/` y se inyectan en `replay`, o en una base de pruebas; nunca se insertan sintéticos en `core` del sistema real.
- [X] T038 [A0] Ejecutar V9, V10, V12, V13 y V14 del quickstart con el sistema real: conteos reales idénticos antes y después de reproducir miles de eventos (V10, con la orden de la spec 005 y su comprobación de aislamiento), reproducción identificada (V9), base caída y recuperación con `docker compose stop postgres` / `start postgres` sin reiniciar la API (V12), validación y CORS (V13), superficie (V14); evidencias `v9-replay.md`, `v10-isolation.md`, `v12-database-down.md`, `v13-validation-cors.md` y `v14-surface.md` en `docs/evidence/006/`.
- [X] T039 [A0] V15: `EXPLAIN (ANALYZE, BUFFERS)` de las consultas de R9 (periodo por defecto, periodo con `min_mag`, país + periodo, estadísticas por hora, `last_ingestion`) con la base de 2025 cargada y, si está disponible, el esquema `bench` de 1.000.000 de filas (spec 002); guardar planes y conclusión en `docs/evidence/006/v15-plans.md`. Si alguna consulta no usa el índice previsto, documentarlo y solo entonces proponer un cambio de modelo con su justificación.
- [X] T040 [A0] V16: ejecutar `python3 tests/benchmark/api_latency.py` en el contenedor `tests`; guardar `docs/evidence/006/v16-latency.md` con equipo, procedimiento, tabla de tres tamaños y la justificación de la agregación por ventanas fijas (R6).
- [X] T041 [P] [US8] [A2] Añadir a `README.md` la sección «Consultar la API» en español con un ejemplo `curl` ejecutable de cada endpoint (`/api/eventos` sin parámetros y con `start`, `end`, `min_mag`, `country_id`; paginación con `limit` y `offset`; `/api/estadisticas`; `/api/salud`), del modo `replay` (incluidos `exclude_synthetic` y la etiqueta «REPRODUCCIÓN») y de los errores 422 y 503; con la forma de leer `metadata`. Fichero exclusivo de esta tarea.
- [X] T042 [US8] [A0] Añadir a `docs/report.md` el apartado «API de consulta» (el contrato implementado, las decisiones R1–R11 resumidas, las dos desviaciones —`not_modified` como consulta correcta y estadísticas completas ante truncado—, la tabla de lo retirado (R8, con el resultado de T032), el traspaso a la spec 007 de `country`/`country_id` y de la propiedad `country`, la medición de latencia y la justificación de las ventanas), enlazando `docs/evidence/006/`.

**Checkpoint**: las evidencias V1–V16 existen con esperado y observado; README y memoria completos.

---

## Phase 11: Cierre

- [X] T043 [A0] Ejecutar la suite completa una sola vez: `pytest tests/unit tests/contract` y después `tests/db` y `tests/query_api` (nunca a la vez), y guardar el resumen en `docs/evidence/006/tests.txt`; si algo falla, corregir el código, no la prueba.
- [X] T044 [A0] Revisar el repositorio antes de versionar: `git status`, que no haya `.env`, datos, `*.bak` ni `*.orig` (nada de datos en Git), que `docs/evidence/006/` no contenga credenciales ni valores de `.env`, que los finales de línea sean LF y que `.specify/feature.json` apunte a `specs/006-query-api`.
- [X] T045 [A0] Actualizar la memoria del proyecto (`MEMORY.md` y el fichero de estado de la spec 006: qué queda hecho, evidencia y comprobaciones pendientes, p. ej. prueba en Linux) y marcar en `specs/006-query-api/tasks.md` lo completado; commit en la rama `006-query-api` con la atribución indicada (sin `git add -A`). *El commit queda pendiente de que la persona autora lo pida.*

---

## Dependencias y orden de ejecución

- **Fases**: 1 → 2 → 3 (US1, MVP) → 4 (US2) → 5 (US3) → 6 (US4) → 7 (US5) → 8 (US6) → 9 (US7) → 10 (US8) → 11. Las historias P2 y P3 dependen de US1 (ruta y filtros); US4 depende además de US2 para el modo `replay`.
- **Ficheros de `[A0]`**: `main.py`, `queries.py`, `db.py`, `filters.py` y el SQL de `stats.py` se editan solo en secuencia por la sesión principal (T003, T004, T007, T009, T010, T014, T018, T021, T023, T024, T029, T033).
- **Paralelismo seguro** (ficheros disjuntos):
  - Fase 2: T005 y T006 en paralelo; T008 también (solo `tests/query_api/`) una vez hecho T004.
  - Fase 3: T011 y T012 en paralelo (ficheros distintos).
  - Fase 4: T015 y T016 en paralelo.
  - Fase 6: T022 (función `compare`) tras T021 y en paralelo con T023; T025 en cuanto exista T024.
  - Fase 10: T036 y T041 en paralelo con la ejecución de evidencias de `[A0]`.
- **Pruebas con base**: las ejecuta `[A0]` una vez por fase (T013, T017, T020, T026, T028, T031, T043); los agentes solo ejecutan `tests/unit` y `tests/contract`.

## Estrategia de implementación

- **MVP**: Fases 1–3 (US1): la API ya devuelve el `FeatureCollection` del contrato con filtros y
  metadatos, suficiente para que la spec 007 empiece a consumirla.
- **Entrega incremental**: añadir US2 (identificar y aislar la reproducción) y US3 (salud y errores
  explícitos) para cerrar los P1; después estadísticas, paginación y acceso (P2); por último la
  limpieza, la evidencia y la documentación (P3).
- **Verificación**: ninguna tarea de evidencia se marca como hecha sin haber ejecutado el
  escenario con el sistema real y guardado esperado y observado en `docs/evidence/006/`
  (principio IX).

## Notas

- Trazabilidad: US1 → FR-001 a FR-008; US2 → FR-009 a FR-014; US3 → FR-015, FR-016, FR-024;
  US4 → FR-017 a FR-023; US5 → FR-006; US6 → FR-025 a FR-027; US7 → FR-028; US8 → FR-029 a
  FR-032.
