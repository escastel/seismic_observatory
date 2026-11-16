---

description: "Task list for feature 005: accelerated replay of a historical selection"
---

# Tasks: Reproducción acelerada de una selección histórica

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/replay-cli.md](contracts/replay-cli.md),
[contracts/replay-message.md](contracts/replay-message.md),
[contracts/synthetic-cases.md](contracts/synthetic-cases.md),
[contracts/isolation-check.md](contracts/isolation-check.md), [quickstart.md](quickstart.md)

**Tests**: incluidas (principio IX, FR-022). Pruebas de comportamiento: comprueban resultados
(filas, mensajes, recuentos, códigos de salida), nunca la presencia de texto en el código.

**Reglas**: código, nombres y comentarios en inglés; documentación y textos de salida de la orden
en español. Finales de línea LF. Nunca leer ni imprimir `.env`; no ejecutar `docker compose
config`. **Sin cambios de modelo** (ni `db/sql/`, ni tablas, ni funciones). Solo se toca el
consumidor en T006. Ningún conjunto descargado en Git. **Nunca dos ejecuciones de `tests/db` a la
vez** (comparten `observatory_test`). `docker compose down -v` pide confirmación explícita.

**Agentes** (etiqueta `[A#]`, norma «Orquestación de agentes» de `CLAUDE.md`):

- `[A0]` sesión principal: consumidor, Docker y base local, memoria, README, evidencias e
  integración final.
- `[A1]` agente nuevo en segundo plano, **Sonnet**: código y pruebas.
- `[A2]` agente nuevo en segundo plano, **Haiku**: tareas mecánicas.

Cada agente recibe un prompt corto que apunta a este fichero y a los contratos (nunca `fork`),
solo toca los ficheros listados en su tarea y ejecuta **solo sus pruebas de `tests/unit`**. Las
pruebas de `tests/db` y la suite completa las ejecuta `[A0]` una vez por fase. Los agentes no
hacen commit, no tocan `.env`, no ejecutan `down -v` y informan en menos de 200 palabras. `[P]` =
paralelizable con otras tareas `[P]` de la misma fase porque sus ficheros no se solapan.

## Format: `[ID] [P?] [Story] [Agente] Description`

---

## Phase 1: Preparación del paquete (bloquea todo)

- [X] T001 [A0] Retirar `producer/app/replay.py` y `tests/unit/test_replay.py` con `git rm` (R9) y crear el paquete `producer/app/replay/` con `__init__.py` y `__main__.py` (este último llama a `cli.main()`). No pueden coexistir el módulo y el paquete con el mismo nombre. Comprobar con `grep` que nada más importa `app.replay` (solo documentación)
- [X] T002 [A0] Añadir el servicio `replay` a `compose.yaml` según [plan.md](plan.md) y [contracts/replay-cli.md](contracts/replay-cli.md): perfil `tools`, imagen del productor (`producer/Dockerfile`), `entrypoint: ["python", "-m", "app.replay"]`, `user: "${LOADER_UID:-0}:${LOADER_GID:-0}"`, variables de base y Kafka como `catalog-loader`, `REPLAY_DEFAULT_RATE: ${REPLAY_DEFAULT_RATE:-50}`, `DATA_DIR: /data`, volumen `./data:/data` (lectura y escritura, para `data/replay/`), `restart: "no"`, red `observatorio`, sin puertos. Sin leer `.env`
- [X] T003 [P] [A2] Añadir `REPLAY_DEFAULT_RATE=50` con comentario en español a `.env.example`, justo después de `KAFKA_TOPIC_REPLAY`. Comprobar que `data/` y `data/replay/` quedan ignorados por Git con `git check-ignore -v data/replay/control.json`. Ficheros: `.env.example`

**Desviaciones de la Fase 1** (menores, sin cambio de modelo):

- T001 retiró también `tests/unit/test_history.py`, que solo probaba el lector del módulo retirado.
- T002 se completó con `ReplaySettings`/`replay()` en `common/settings.py` (base de datos de
  escritura, Kafka, `DATA_DIR` y `REPLAY_DEFAULT_RATE`) y su prueba en
  `tests/unit/test_common_settings.py`; el plan no listaba `common/` pero la orden necesita una
  configuración propia sin URL del feed.
- `tests/integration/load_test.py` (`check_replay`) llama a la orden antigua `app.replay --path`;
  se adapta en T025 a la orden nueva.

**Checkpoint**: el paquete existe y el servicio está declarado; nada publica todavía.

---

## Phase 2: Fundamentos compartidos (bloquea las historias)

- [X] T004 [P] [A1] Implementar `producer/app/replay/pacing.py` según R6: `interval(previous_time_ms, next_time_ms, rate, speedup)` devuelve los segundos entre dos publicaciones. Solo `rate`: `1/rate`. Con `speedup`: `(next-previous)/1000/speedup`; si además hay `rate`, `max(original/speedup, 1/rate)` (la cadencia nunca supera la velocidad indicada). `rate` y `speedup` deben ser **«> 0 y finito»**: `ValueError` con mensaje en español si no. Un intervalo original negativo (eventos con el mismo tiempo o desordenados) vale 0 antes del `max`. Incluir un `Schedule` con plazos absolutos sobre un reloj inyectable (monótono) que, tras una pausa, rebasa los plazos para no emitir en ráfaga. Pruebas en `tests/unit/test_replay_pacing.py`: solo `rate`, con `speedup`, con ambos (tope), valores inválidos (0, negativo, NaN, inf), intervalo negativo, y el rebase tras una pausa con reloj falso. Ficheros: `producer/app/replay/pacing.py`, `tests/unit/test_replay_pacing.py`
- [X] T005 [P] [A1] Implementar `producer/app/replay/message.py` según [contracts/replay-message.md](contracts/replay-message.md): `build_replay_message(feature, *, extraction_id, replayed_at, run)` devuelve el diccionario con `id`, `updated`, `time`, `mag`, `place`, `geometry`, `properties`, `original_event`, `source = "usgs_catalog"`, `ingested_at` (igual que `replayed_at`), `mode = "replay"`, `extraction_id` (puede ser `None`), `replayed_at` (ISO 8601 UTC con `Z`) y `replay_run`; y `encode()` (JSON compacto UTF-8, `allow_nan=False`, igual que `producer/app/publisher.py`). `time` y `updated` salen de `properties` **sin modificar** (principio VI). Pruebas en `tests/unit/test_replay_message.py`: `time` y `updated` idénticos a los del `Feature` para varios eventos (incluido uno con `mag` nula), `mode`, `replayed_at` en UTC con `Z`, clave = `id`, `NaN` rechazado. Ficheros: `producer/app/replay/message.py`, `tests/unit/test_replay_message.py`
- [X] T006 [A0] Ajuste mínimo del consumidor (R1): en `consumer/app/main.py`, `MessageHandler._write` usa el `replayed_at` del mensaje si el topic es el de reproducción y el campo es una fecha ISO 8601 válida con zona; si falta o no es válido, `datetime.now(timezone.utc)` como hasta ahora. Pasar el mensaje ya decodificado a `_write` sin cambiar nada más. Prueba en `tests/db/test_replay_replayed_at.py`: un mensaje del topic de reproducción con `replayed_at` fijo lo deja en `replay.event_current.replayed_at`; sin el campo usa una hora de lectura reciente; con un valor ilegible usa la hora de lectura y **no** va a cuarentena; un mensaje del topic real con ese campo lo ignora (`core.event_current.replayed_at` sigue nulo). Ficheros: `consumer/app/main.py`, `tests/db/test_replay_replayed_at.py`
- [X] T007 [P] [A1] Implementar `producer/app/replay/control.py` según [data-model.md](data-model.md) §4 y §5: `write_control(dir, command)` con `command ∈ {"pause","resume","stop"}` y `requested_at` UTC; `read_control(dir)` devuelve la orden o `None`; `consume_control(dir)` la lee y la borra; `write_status(dir, **fields)` y `read_status(dir)` con los campos `run`, `state` (**`running`, `paused`, `stopped`, `finished` o `failed`**), `total`, `sent`, `remaining`, `rate_target`, `speedup`, `started_at`, `updated_at`, `extraction_id`, `error`. Escritura atómica (fichero temporal más `os.replace`) con `newline="\n"`; directorio `data/replay/` creado si falta. Una orden desconocida es `ValueError`. Pruebas en `tests/unit/test_replay_control.py` con `tmp_path`: ida y vuelta, consumo único, orden inválida, estado atómico (nunca un JSON a medias al leer mientras se escribe), directorio inexistente. Ficheros: `producer/app/replay/control.py`, `tests/unit/test_replay_control.py`

**Checkpoint**: cadencia, mensaje, control y consumidor listos y probados de forma aislada.

---

## Phase 3: US1 · Reproducir una selección sin tocar los datos reales (P1) 🎯 MVP

**Goal**: seleccionar de lo descargado, registrar la selección, publicar acelerado y demostrar que
`core` no cambia.

**Independent test**: reproducir ≥ 5.000 eventos y comparar `core` antes y después (V1, V2, V3, V8).

- [X] T008 [A1] Implementar la parte pura de `producer/app/replay/selection.py` según R2, R7 y [contracts/replay-cli.md](contracts/replay-cli.md): `Selection` (parámetros, eventos, huella del conjunto) y `select_events(files, start, end, min_mag, bbox)` que lee los `FeatureCollection` de los ficheros dados, filtra por tiempo (`start` incluido, `end` **excluido**), por `min_mag` (las magnitudes nulas **no** cumplen el filtro y se cuentan en `without_magnitude_dropped`) y por `bbox` `(min_lon, min_lat, max_lon, max_lat)` (**`min` < `max`; sin cruce del antimeridiano**, `ValueError` en español si no), deduplica por `id` quedándose con el `updated` mayor, ordena por `time` ascendente y `id` como desempate, y calcula `content_sha256` = SHA-256 del conjunto ordenado de pares `id:updated`. Reutilizar `producer/app/fingerprint.py`. Pruebas en `tests/unit/test_replay_selection.py` con ficheros GeoJSON pequeños en `tmp_path`: filtros de periodo (borde final excluido), magnitud mínima y nulas contadas, recuadro, evento repetido en dos ficheros (se queda el `updated` mayor), orden, selección vacía y huella estable. Ficheros: `producer/app/replay/selection.py`, `tests/unit/test_replay_selection.py`
- [X] T009 [A1] Ampliar `producer/app/replay/selection.py` con la verificación y el registro (R7, R8, principio V): `locate_files(conn, data_dir, start, end, min_mag)` busca en `core.extraction` las cargas `purpose = 'historical_load'` con `outcome = 'ok'` que cubran el periodo (con `window_start/end`) y su fichero en `core.raw_payload` (`encoding = 'file'`); **falla con `SelectionRejected` (código 2)** si el periodo no está cubierto, si la magnitud mínima pedida es menor que la de la carga (`request_params->>'minmagnitude'`) o si la huella del fichero no coincide con `content_sha256` (`producer/app/fingerprint.py`). `register_selection(conn, selection)` inserta **una fila** en `core.extraction` con `source = 'usgs_catalog'`, `purpose = 'replay_selection'`, `request_url = 'local-catalog:data/usgs/catalog'`, `outcome = 'ok'`, `window_start/end`, `request_params` (`start`, `end`, `min_magnitude`, `bbox`, `files` con ruta y huella, `without_magnitude_dropped`), `record_count` y `earthquake_count` = número de eventos, `excluded_count = 0`, `content_sha256`; `set_published_count` al terminar. Una selección vacía se registra con 0 eventos. Un rechazo no registra fila. Pruebas en `tests/db/test_replay_selection.py` (las ejecuta `[A0]`): fila registrada con sus parámetros y recuento, selección vacía con 0 eventos, rechazo por fichero alterado (copia en `tmp_path`), por periodo sin cobertura y por magnitud insuficiente, sin llamadas de red. Ficheros: `producer/app/replay/selection.py`, `tests/db/test_replay_selection.py`
- [X] T010 [P] [A1] Implementar `producer/app/replay/isolation.py` según [contracts/isolation-check.md](contracts/isolation-check.md) y R5: `take_snapshot(conn)` descubre las tablas de `core` en `pg_catalog` y devuelve, por tabla, `rows` y `checksum` (`count(*)` y `coalesce(sum(hashtextextended(t::text, 0)::numeric), 0)`), con `WHERE purpose <> 'replay_selection'` en `core.extraction` y el número de filas `replay_selection` aparte; `compare(snapshot, current)` devuelve las diferencias; `save/load` a `data/replay/core-snapshot.json` con `newline="\n"`. Pruebas en `tests/db/test_replay_isolation_check.py` (las ejecuta `[A0]`): idéntica sin cambios, detecta una fila alterada, una insertada y una borrada en `core.event_current`, ignora filas `replay_selection` nuevas, incluye una tabla creada en la prueba. Ficheros: `producer/app/replay/isolation.py`, `tests/db/test_replay_isolation_check.py`
- [X] T011 [A1] Implementar `producer/app/replay/runner.py`: `run_replay(producer, events, *, topic, extraction_id, rate, speedup, control_dir, lock, clock, sleep, run_id)` con `producer` y `lock` inyectables (Protocols como en `producer/app/publisher.py`). Publica en orden con `send_and_wait` (clave `id` UTF-8, valor de `message.build_replay_message` y `encode`), **espera la confirmación de cada mensaje** (principio II; si Kafka falla, estado `failed` y no publica los siguientes), usa `Schedule` de `pacing.py`, escribe `status.json` cada segundo y en cada cambio de estado, y devuelve el número confirmado. Estados: `running` → `finished` al terminar. Esta tarea **no** implementa aún pausa, parada ni bloqueo (US2). Pruebas en `tests/unit/test_replay_runner.py` con `FakeProducer` (como `tests/support/fake_kafka.py`) y reloj falso: orden de publicación, clave, `time`/`updated` intactos, `replayed_at` presente, cadencia con reloj falso dentro del ±20 %, fallo de Kafka a mitad (`failed`, sin más envíos, `sent` correcto), selección vacía (no publica, `finished`). Ficheros: `producer/app/replay/runner.py`, `tests/unit/test_replay_runner.py`
- [X] T012 [A1] Implementar `producer/app/replay/cli.py` (subórdenes de esta fase): `select`, `start` (sin `--synthetic*` ni control todavía), `snapshot` y `compare`, con `argparse`, opciones y validaciones de [contracts/replay-cli.md](contracts/replay-cli.md) (`--start`, `--end`, `--min-mag`, `--bbox`, `--rate` con valor por defecto `REPLAY_DEFAULT_RATE` o 50, `--speedup`), **códigos de salida** 0, 1 (uso), 2 (selección rechazada), 5 (fallo de Kafka o de base) y 6 (`compare` con diferencias), y textos de salida en español. Usa `common.settings`, `common.db.create_pool` y `common.topics.ensure_topics` como `producer/app/catalog_load.py`. Pruebas en `tests/unit/test_replay_cli.py`: análisis de argumentos (válidos e inválidos: `--rate 0`, `--bbox` con min > max, `--end` ≤ `--start`), código de salida de cada error con dependencias falsas, mensaje en español. Ficheros: `producer/app/replay/cli.py`, `tests/unit/test_replay_cli.py`
- [X] T013 [A0] Prueba de comportamiento de extremo a extremo con la base real y Kafka simulado en `tests/db/test_replay_end_to_end.py`: genera ≥ 200 eventos de un catálogo falso en `tmp_path` registrado en `core.extraction`/`core.raw_payload`, ejecuta `select` + `run_replay` con un productor falso que entrega cada mensaje a `MessageHandler` del consumidor con el `search_path` de reproducción, y comprueba: recuento de `replay.event_current` = eventos distintos de la selección; `event_time` y `updated_at` iguales a los del fichero; `replayed_at` no nulo en todas las filas; `kafka_topic = 'earthquakes.replay'` en todas las versiones; instantánea de `core` idéntica antes y después; un mismo `event_id` insertado antes en `core` con otros valores convive con su versión en `replay` sin modificarse. Ficheros: `tests/db/test_replay_end_to_end.py`
- [X] T014 [A0] Ejecutar `pytest tests/unit -q` y, una sola vez, `pytest tests/db -q` en el contenedor `tests` (con `docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm tests pytest …`); corregir o devolver al agente lo que falle. Comprobar que las pruebas previas siguen en verde. Guardar el resultado en `docs/evidence/005/tests-phase3-6.txt` (una sola ejecución de las Fases 3 a 6)

**Checkpoint**: se puede seleccionar, registrar y publicar; `core` demostrado intacto con la base real y Kafka simulado.

---

## Phase 4: US2 · Controlar la reproducción (P1)

**Goal**: pausar, reanudar, detener y repetir desde cero, con una sola reproducción activa.

**Independent test**: V4 y V5.

- [X] T015 [A1] Ampliar `producer/app/replay/runner.py` con el control: en cada espera y entre envíos consulta `control.consume_control` cada ≤ 0,25 s; `pause` → estado `paused`, no publica ni cambia `sent` y rebasa el `Schedule` al reanudar; `resume` → continúa por el **siguiente** evento sin saltar ni repetir; `stop` → estado `stopped`, lo publicado se conserva y `published_count` queda fijado. `start` borra una orden de control antigua al empezar. Pruebas en `tests/unit/test_replay_runner.py` (ampliar): pausa efectiva en menos de 2 s con reloj falso, ningún envío en pausa, reanudar sin saltos ni repeticiones (secuencia de `id` publicada igual a la selección), `stop` en pausa y en marcha, una orden antigua previa no afecta a la ejecución nueva. Ficheros: `producer/app/replay/runner.py`, `tests/unit/test_replay_runner.py`
- [X] T016 [A1] Implementar el bloqueo de una sola reproducción activa (R4) en `producer/app/replay/runner.py` y `producer/app/replay/cli.py`: `ActiveRunLock` sobre `pg_try_advisory_lock` con una clave constante, en una conexión que `start` mantiene mientras corre y que se libera al terminar o al morir el proceso. Si está ocupado, `start` termina con **código 4** sin publicar ni registrar selección. `reset` toma el mismo bloqueo; si está ocupado, **código 4**; si está libre, llama a `replay.reset()` con el escritor y termina con 0. Añadir las subórdenes `pause`, `resume`, `stop` (código **3** si no hay reproducción activa: sin fichero de estado en estado `running` o `paused`) y `status` (imprime estado, enviados, restantes y objetivo de velocidad en español). Pruebas en `tests/db/test_replay_lock.py` (las ejecuta `[A0]`): dos `start` a la vez → el segundo recibe 4; el bloqueo se libera al terminar y al cerrar la conexión; `reset` con el bloqueo ocupado → 4; `reset` libre vacía las tablas de `replay` y no cambia la instantánea de `core`; `core` no tiene función `reset`. Ficheros: `producer/app/replay/runner.py`, `producer/app/replay/cli.py`, `tests/db/test_replay_lock.py`
- [X] T017 [A0] Prueba de comportamiento en `tests/db/test_replay_control_flow.py`: con la base real y Kafka simulado, ejecutar una reproducción, pausar a mitad, comprobar que la base no recibe más versiones, reanudar y terminar; detener otra a mitad; `reset` + repetición con el mismo resultado final (recuento y suma de `replay.event_current`) y `core` idéntico en cada paso. Ficheros: `tests/db/test_replay_control_flow.py`
- [X] T018 [A0] Ejecutar `pytest tests/db -q` una vez y `pytest tests/unit -q`; guardar `docs/evidence/005/tests-phase4.txt`

**Checkpoint**: control completo y repetición desde cero probados.

---

## Phase 5: US3 · Casos sintéticos controlados (P2)

**Goal**: cinco casos con resultado conocido (7 mensajes), comprobables con consultas.

**Independent test**: V6.

- [X] T019 [A1] Implementar `producer/app/replay/synthetic.py` según [contracts/synthetic-cases.md](contracts/synthetic-cases.md) y R10: `synthetic_messages(replayed_at, run)` devuelve, **en este orden fijo**, los siete mensajes con fechas fijas del 2025-06-15 UTC, identificadores `synthetic-replay-first`, `synthetic-replay-revised`, `synthetic-replay-stale` y `synthetic-replay-bad-coordinates`, `"synthetic": true`, `"synthetic_case"` y `mode = "replay"`; U1 = 2025-06-15 12:10 UTC y U2 = 2025-06-15 13:30 UTC; magnitud 4,1 y 4,4 en la revisión; latitud 145 en el caso de cuarentena. Seguir las claves de `tests/synthetic/cases.py` (`base()`), sin importar nada de `tests/`. Pruebas en `tests/unit/test_replay_synthetic.py`: siete mensajes, orden, repetición exacta byte a byte del primero, `updated` de la versión tardía anterior a la nueva, todos con el prefijo y la marca, fechas independientes de «ahora». Ficheros: `producer/app/replay/synthetic.py`, `tests/unit/test_replay_synthetic.py`
- [X] T020 [A1] Añadir `--synthetic` (los siete mensajes **después** de la selección) y `--synthetic-only` (solo ellos, **sin selección ni fila de extracción**, `extraction_id = null`; incompatible con `--start`, `--end`, `--min-mag` y `--bbox`, código 1) a `producer/app/replay/cli.py` y `producer/app/replay/runner.py`. El contador `total` y el progreso incluyen los sintéticos. Pruebas en `tests/unit/test_replay_cli.py` (ampliar): combinaciones válidas e inválidas y que `--synthetic-only` no registra extracción. Ficheros: `producer/app/replay/cli.py`, `producer/app/replay/runner.py`, `tests/unit/test_replay_cli.py`
- [X] T021 [A0] Prueba de comportamiento en `tests/db/test_replay_synthetic.py` con la base real y los mensajes pasados por `MessageHandler`: tras reproducir solo los sintéticos, `message_log` de los siete mensajes tiene `new` 3, `duplicate` 1, `revised` 1, `stale` 1 y `quarantined` 1; `replay.event_current` tiene 3 filas con `first` (mag 4,1), `revised` (mag 4,4, `updated_at` = U2) y `stale` (`updated_at` = U2, no retrocede); `replay.event_version` tiene 5 filas; `replay.quarantine` tiene 1 fila con `is_synthetic` y `reason_codes` que incluye `coordinates_out_of_range`; **ninguna** fila `synthetic-replay-%` en `core`. Las consultas son las de [contracts/synthetic-cases.md](contracts/synthetic-cases.md). Ficheros: `tests/db/test_replay_synthetic.py`

**Checkpoint**: los cinco casos demuestran sus resultados con consultas.

---

## Phase 6: US4 · Reinicio del consumidor a mitad (P2)

**Goal**: el resultado final no depende de que el consumidor se reinicie.

**Independent test**: V7 (sistema real).

- [X] T022 [A0] Prueba de comportamiento en `tests/db/test_replay_consumer_restart.py`: procesar con `MessageHandler` la primera mitad de los mensajes de una reproducción, «reiniciar» (manejador nuevo) releyendo desde la mitad con solapamiento (mensajes ya procesados incluidos, como ocurre con «al menos una vez»), y comprobar que recuento y suma de `replay.event_current` y de `replay.event_version` son iguales a los de una ejecución sin reinicio; `replayed_at` no cambia en los mensajes releídos (R1). Ficheros: `tests/db/test_replay_consumer_restart.py`

**Checkpoint**: idempotencia probada con la base real; el reinicio del contenedor se prueba en la Fase 8.

---

## Phase 7: US5 · Documentación, material heredado y demostración (P3)

**Goal**: entrega coherente y reproducible por otra persona.

**Independent test**: V9 y seguir el README desde cero.

- [X] T023 [P] [A2] Retirar `db/seeds/historical_2025.jsonl` y `db/seeds/historical_1900.jsonl` de Git con `git rm` (R9; el segundo es un conjunto descargado, regenerable con `docker compose run --rm catalog-loader`) y reescribir `db/seeds/README.md` en español: la carpeta queda sin lotes versionados, explica por qué, dónde van los conjuntos descargados (`data/`, ignorado), cómo regenerarlos (enlace al README de la raíz y a `specs/003-usgs-ingestion/contracts/catalog-loader.md`) y cómo se reproduce ahora (enlace a esta spec). Mantener `.gitkeep`. No tocar `.gitignore`. Comprobar con `git ls-files db/seeds` que solo quedan `.gitkeep` y `README.md`. Ficheros: `db/seeds/historical_1900.jsonl`, `db/seeds/historical_2025.jsonl`, `db/seeds/README.md`
- [X] T024 [P] [A2] Revisar las referencias a los lotes retirados y a `producer/app/replay.py` en `docs/calidad.md`, `docs/evidence/` y `specs/001-streaming-sismos-etl/`: **no reescribir evidencias ni specs anteriores** (son históricas); listar en un informe corto qué ficheros las mencionan y cuáles de ellos son documentación viva (`docs/calidad.md`, `README.md`) para que `[A0]` los actualice. Solo lectura. Ficheros: ninguno (informe)
- [X] T025 [A0] Actualizar los enlaces rotos que T024 detecte en documentación viva (`docs/calidad.md`) y el `README.md` en la sección «Cargar el histórico» si apunta a los lotes retirados; adaptar `check_replay` de `tests/integration/load_test.py` a la orden nueva (`docker compose run --rm replay start …`, servicio `replay`) o retirar su parte de reproducción si ya no mide nada útil. Ficheros: `docs/calidad.md`, `README.md`, `tests/integration/load_test.py`, `.gitignore` (T024 detectó dos excepciones `!db/seeds/historical_*` que ya no apuntan a nada)

**Checkpoint**: sin conjuntos descargados en Git y sin enlaces rotos.

---

## Phase 8: Verificación con el sistema real y evidencia (sesión principal)

Con la skill `verify-stack`. Cada escenario guarda esperado, observado y salida en
`docs/evidence/005/` y no se declara superado sin ellos (principio IX).

- [X] T026 [A0] Levantar el stack (`docker compose up --build -d`), esperar a los cinco servicios sanos, comprobar que el catálogo 2025 con magnitud ≥ 4 está en `data/usgs/catalog/` y registrado (si no, `docker compose run --rm catalog-loader`) y que el periodo elegido tiene al menos 5.000 eventos con `replay select`. Guardar `docs/evidence/005/00-environment.md`. Antes de cualquier `down -v`, pedir confirmación
- [X] T027 [A0] V1: selección registrada y verificada, con sus tres rechazos (periodo sin cobertura, magnitud insuficiente, fichero alterado en una **copia**) y la selección vacía. Evidencia `docs/evidence/005/v1-selection.md`
- [X] T028 [A0] V2 y V8: reproducción de ≥ 5.000 eventos con `--rate 200`; recuento de `replay.event_current`, cadencia medida (±20 %), `time` y `updated` contra el fichero, `replayed_at` no nulo, `kafka_topic` y consulta del mismo identificador en `core` y `replay`. Evidencia `docs/evidence/005/v2-replay-5000.md`
- [X] T029 [A0] V3: aislamiento. `docker compose stop producer`, `snapshot`, reproducción, `compare` (0 tablas con diferencias), `reset`, nueva reproducción, `compare`, `docker compose start producer`. Evidencia `docs/evidence/005/v3-isolation.md`
- [X] T030 [A0] V4: pausa, reanudación y parada con dos terminales; tiempo hasta la pausa efectiva (< 2 s); `start` simultáneo rechazado con código 4; `reset` con reproducción activa rechazado. Evidencia `docs/evidence/005/v4-control.md`
- [X] T031 [A0] V5: repetición tras `reset` con recuento y suma de comprobación iguales a los de V2. Evidencia `docs/evidence/005/v5-repeat.md`
- [X] T032 [A0] V6: casos sintéticos con `--synthetic-only` y las consultas de [contracts/synthetic-cases.md](contracts/synthetic-cases.md). Evidencia `docs/evidence/005/v6-synthetic.md`
- [X] T033 [A0] V7: reinicio real del consumidor a mitad de una reproducción (`docker compose restart consumer`); comparar recuento y suma con V2. Evidencia `docs/evidence/005/v7-consumer-restart.md`
- [X] T034 [A0] V9: `git ls-files db/seeds`, `git status --short` y comprobación de que ningún fichero de `data/` está versionado. Evidencia `docs/evidence/005/v9-repository.md`
- [X] T035 [A0] Ejecutar la suite completa una vez (`pytest tests -q` en el contenedor `tests`) y guardar `docs/evidence/005/tests.txt`; escribir `docs/evidence/005/README.md` con el índice de escenarios, lo esperado, lo observado y la revisión contra los principios II, III, VI y VII

---

## Phase 9: Memoria y README (sesión principal)

- [X] T036 [A0] Añadir a `docs/report.md` el apartado «Reproducción histórica» en español: objetivo, diseño (selección, publicación, control, aislamiento), decisiones R1 a R12 resumidas, la excepción justificada de `core.extraction`, el cambio mínimo del consumidor, los resultados medidos de la Fase 8 (distinguiendo medido de supuesto, con equipo y procedimiento) y el destino del material heredado. Ficheros: `docs/report.md`
- [X] T037 [A0] Añadir a `README.md` la sección «Demostración de la defensa»: requisitos, paso a paso con las órdenes exactas de [quickstart.md](quickstart.md) (seleccionar, reproducir, pausar, reanudar, detener, repetir con `reset`, comprobar el aislamiento y los casos sintéticos), qué se verá en la base y la advertencia de parar el productor para la comprobación de aislamiento. Comprobar el procedimiento siguiéndolo desde un sistema levantado (SC-001: menos de 5 minutos). Ficheros: `README.md`
- [X] T038 [A0] Revisión final: `git status` (sin `.env`, `data/` ni copias), `git diff --stat` revisado, todas las tareas marcadas, `docs/evidence/005/` completo, `specs/005-historical-replay/checklists/requirements.md` coherente y actualización de la memoria del proyecto (`MEMORY.md`: spec 005 hecha y siguiente 006). Preparar el commit por fases sin `git add -A`, con la atribución indicada

---

## Dependencias y orden

```text
Fase 1 (T001–T003) ─► Fase 2 (T004–T007) ─► Fase 3 (US1) ─► Fase 4 (US2) ─► Fase 5 (US3) ─► Fase 6 (US4)
                                                                                         │
                        Fase 7 (T023–T025, independiente) ───────────────────────────────┤
                                                                                         ▼
                                                        Fase 8 (verificación real) ─► Fase 9 (memoria y README)
```

- T001 antes de cualquier tarea de `producer/app/replay/`.
- T004, T005, T007 son paralelizables entre sí; T006 es de la sesión principal y usa `tests/db`.
- Dentro de la Fase 3: T008 → T009 → T012; T010 y T011 son independientes de T009 pero T011 necesita
  T004 y T005; T012 necesita T008, T009, T010 y T011; T013 necesita T012.
- Los ficheros compartidos entre tareas (`runner.py`, `cli.py`, `selection.py`) obligan a ejecutar
  esas tareas **en secuencia**, no en paralelo: T008→T009, T011→T015→T016→T020 y T012→T016→T020.
- La Fase 7 solo toca documentación y `db/seeds/`, y puede ir en paralelo con las Fases 3 a 6.
- Ninguna tarea de las Fases 8 y 9 empieza hasta que T014, T018, T021 y T022 estén en verde.

### Paralelismo por agente

- **Fase 2**: T004 + T005 + T007 a la vez (tres agentes Sonnet, ficheros distintos); T003 con Haiku.
- **Fase 3**: T008 y T010 a la vez; luego T009 y T011 a la vez; luego T012. Los tests de
  `tests/db` de T009 y T010 los ejecuta `[A0]` en secuencia.
- **Fase 7**: T023 y T024 a la vez con Haiku, durante las fases 3 a 6.

## Estrategia de implementación

1. **MVP = Fase 1 + 2 + 3 (US1)**: reproducir una selección registrada y comprobar el aislamiento.
   Con eso ya hay demostración posible, aunque sin control.
2. Añadir US2 (control y repetición): la demostración pasa a ser repetible.
3. Añadir US3 y US4 (sintéticos y reinicio): demuestran las reglas de idempotencia.
4. US5 y la verificación real cierran la entrega; hasta T035 ninguna prueba se da por superada.
5. Una spec por sesión: si la ejecución se interrumpe, reanudar desde la primera tarea sin marcar,
   leyendo solo este fichero y los contratos que cite.

## Resumen

- 38 tareas: Fase 1 (3), Fase 2 (4), US1 (7), US2 (4), US3 (3), US4 (1), US5 (3), verificación
  real (10) y memoria y README (3).
- Agentes: `[A0]` 23 tareas, `[A1]` 12 tareas, `[A2]` 3 tareas.
