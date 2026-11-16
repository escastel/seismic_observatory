---

description: "Task list for feature 004: consumer and data quality"
---

# Tasks: Consumidor y calidad de los datos

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/rules-catalog.md](contracts/rules-catalog.md),
[contracts/reprocess.md](contracts/reprocess.md), [quickstart.md](quickstart.md)

**Tests**: incluidas (principio IX). Las pruebas van antes que el código que las satisface.

**Reglas**: código, nombres y comentarios en inglés; documentación en español. No se toca
`producer/`, `api/`, `frontend/` ni `common/`. Nunca leer ni imprimir `.env`. **Nunca dos
ejecuciones de `tests/db` a la vez** (comparten `observatory_test`). `docker compose down -v` pide
confirmación.

**Agentes** (etiqueta `[A#]`, ver «Orquestación»): cada agente solo toca los ficheros de sus
tareas y ejecuta únicamente sus pruebas; la ejecución completa la hace el orquestador.

## Format: `[ID] [P?] [Story] [Agente] Description`

---

## Phase 1: Modelo (bloquea todo)

- [X] T001 [A0] Crear `db/sql/041_consumer_quality.sql` como plantilla por esquema, **idempotente**, según [data-model.md](data-model.md) §1: en `quarantine`, `reprocessed_at timestamptz`, `reprocess_result text` con `CHECK` en (`recovered_new`,`recovered_revised`,`recovered_stale`,`recovered_duplicate`,`still_rejected`), `reprocess_reason_codes text[]` y `CHECK ((reprocessed_at IS NULL) = (reprocess_result IS NULL))`; en `message_log`, `attempt smallint NOT NULL DEFAULT 0`, clave primaria `(kafka_topic, kafka_partition, kafka_offset, attempt)` (bloque `DO` que solo la recrea si no incluye `attempt`) y `outcome` con `excluded` además de los cinco valores. Usar `IF NOT EXISTS` y `DROP CONSTRAINT IF EXISTS`
- [X] T002 [A0] Actualizar `db/sql/apply.sh`: `041_consumer_quality.sql` en la lista de plantillas y un segundo argumento opcional con el nombre de un único fichero a aplicar (para el volumen existente), sin SQL propio
- [X] T003 [A0] Actualizar `db/sql/070_grants.sql` solo si hace falta (el escritor ya tiene `UPDATE` en las tablas) y `specs/002-platform-data-model/contracts/database.md` con `attempt` y `excluded`
- [X] T004 [A0] Actualizar las sentencias `ON CONFLICT (kafka_topic, kafka_partition, kafka_offset)` de `message_log` en `tests/db/helpers.py`, `consumer/app/persistence.py` y las pruebas que las usen para `... , attempt`; ejecutar `pytest tests/db -q` y comprobar que las 303 pruebas previas siguen en verde, y que `apply.sh` se puede aplicar dos veces seguidas a `observatory_test` sin error
- [X] T005 [A0] Añadir a `tests/db/test_message_counts.py` las pruebas del modelo: dos filas con el mismo mensaje y `attempt` 0 y 1 conviven; un tercer `attempt = 1` igual no; `outcome = 'excluded'` se admite; `reprocess_result` fuera de valores se rechaza; `reprocessed_at` sin resultado se rechaza

**Checkpoint**: el modelo admite el reprocesado y la exclusión; la 002 y la 003 siguen en verde.

---

## Phase 2: US1 · Reglas (P1) 🎯 MVP

**Goal**: solo lo intratable va a cuarentena; lo demás se conserva, con marcas.
**Independent Test**: V1 de [quickstart.md](quickstart.md).

- [ ] T006 [P] [US1] [A1] Crear `tests/unit/test_rules.py` con una tabla de casos por cada regla de [contracts/rules-catalog.md](contracts/rules-catalog.md): mensaje de entrada → (efecto, códigos o marcas, valores guardados). Casos mínimos: magnitud nula (nulo, sin marca), `magType` y profundidad nulos, magnitud −0,5 (sin marca), profundidad −2,7 (`negative_depth`), magnitud 10,5 y −3 (`magnitude_out_of_range`), profundidad 900 (`depth_out_of_range`), evento de hace 30 días (sin marca), tiempo futuro a 10 min (`future_time`) y a 2 min (sin marca), `updated` < `time`, magnitud `"4.2"` (4.2 + `magnitude_from_text`) y `"abc"` (nulo + `magnitude_not_numeric`), 4 coordenadas, latitud 145, longitud −200, límites 180/−90 válidos, NaN, geometría `LineString`, sin `id`, sin `time`, `updated` texto, varios motivos a la vez (todos listados), JSON no objeto, tipo `quarry blast` (exclusión `not_earthquake`), sin tipo (`missing_type`), mensaje con `synthetic: true` (marca `synthetic`/`is_synthetic`). Debe fallar antes de implementar
- [ ] T007 [P] [US1] [A1] Crear `tests/unit/test_rules_catalog.py`: los códigos de `consumer/app/rules.py` coinciden exactamente con los de las tablas de [contracts/rules-catalog.md](contracts/rules-catalog.md) (se leen del documento), cada regla tiene dimensión de las seis del enunciado y el catálogo no incluye `magnitude_null`, `event_too_old`, `future_timestamp` ni `duplicate_id`
- [ ] T008 [US1] [A1] Crear `consumer/app/rules.py` hasta que T006 y T007 pasen: catálogo como datos (código, dimensión, efecto, descripción), `evaluate(raw_bytes, received_at)` que devuelve una de `Quarantine(reasons, detail, payload|raw_text)`, `Exclusion(reason, event)` o `Accepted(event, flags)`, evaluando **todas** las reglas de cuarentena sin cortar en la primera; conversión de milisegundos a UTC; sin `NaN` ni `Infinity`; el `synthetic: true` del mensaje añade la marca. Eliminar `consumer/app/quality.py` y `tests/unit/test_quality.py` (sustituidos)
- [ ] T009 [US1] [A1] Adaptar `consumer/app/persistence.py` y `consumer/app/main.py` a `rules.evaluate`: pasar las marcas a `apply_event_version` (`p_quality_flags`), escribir `excluded_event` con `ON CONFLICT DO NOTHING` y la extracción solo si existe, resultado `excluded` en `message_log`, `is_synthetic` en cuarentena, `model_constraint_violation` con el error de la base, y conservar la transacción por mensaje, el commit del offset después y los reintentos de conexión; actualizar `tests/unit/test_consumer_loop.py` si hace falta
- [ ] T010 [US1] [A1] Crear `tests/db/test_consumer_rules.py` con el `MessageHandler` real contra `observatory_test` (como `test_consumer_persistence.py`): cada caso de T006 acaba en su tabla con sus códigos y marcas; varios motivos = una fila de cuarentena con todos; fecha anterior a 1900 = `model_constraint_violation` y el siguiente mensaje se procesa; los tres topics aplican las mismas reglas (replay a su esquema); un mensaje defectuoso no retrasa al siguiente más de 1 s; ejecutar hasta que pase y corregir `tests/db/test_consumer_persistence.py` si usaba reglas retiradas

**Checkpoint**: magnitud nula, negativa, profundidad negativa y evento antiguo entran como eventos (SC-002).

---

## Phase 3: US3 · País (P1)

**Independent Test**: V5.

- [X] T011 [P] [US3] [A2] Reescribir `tests/unit/test_spatial.py` con el catálogo real `frontend/public/datos/paises.geojson`: punto interior (`ESP`, `JPN`), océano (nulo y sin ambigüedad), un punto sobre una frontera terrestre real (el resultado es la entidad de `ADM0_A3` menor y `ambiguous=True`; calcular el punto buscando dos entidades que se tocan en el propio catálogo, no a mano), 100 puntos repartidos por el mundo con dos ejecuciones idénticas (SC-005), catálogo con `ADM0_A3` repetido o ausente (lanza `CatalogError` nombrando los identificadores), catálogo con identificador que no está en una lista de la dimensión (error)
- [X] T012 [US3] [A2] Reescribir `consumer/app/spatial.py` hasta que T011 pase: `lookup(lon, lat)` devuelve `(country_id | None, ambiguous: bool)` con todas las coincidencias de `intersects` ordenadas por `ADM0_A3`; comprobación de unicidad y de presencia en `core.dim_country` al construir (función `verify_against_dimension(pool)` llamada en `main.run` antes de consumir; el consumidor termina con mensaje claro si falla); la marca `ambiguous_country` la añade `rules`/`main` (acordar la interfaz con T008: `lookup` se llama después de `evaluate`)
- [ ] T013 [US3] [A2] Añadir a `tests/db/test_consumer_rules.py` (en una función aparte, sin tocar las de T010) los casos con país: evento en el interior recibe `country_id` existente en `dim_country`, evento marítimo país nulo y permanece en `event_current`, punto ambiguo lleva `ambiguous_country`; ejecutar solo ese fichero cuando A1 haya terminado

---

## Phase 4: US2 · Reprocesar (P1)

**Independent Test**: V4.

- [ ] T014 [P] [US2] [A3] Crear `tests/db/test_reprocess.py`: fila rechazada solo por magnitud nula se recupera (`recovered_new`) en el espacio de su topic, con su fila `attempt = 1` y sin borrar la de cuarentena ni la `attempt = 0`; fila con coordenadas inválidas queda `still_rejected` con `reprocess_reason_codes`; segunda ejecución no cambia ningún recuento; fila de replay se recupera en `replay`; evento con versión posterior ya existente da `recovered_stale` y el estado no cambia; fila con `raw_text` sigue rechazada; fila sintética se recupera con su evento marcado `synthetic`; `--dry-run` no escribe; ejecutar dos reprocesados concurrentes termina con el mismo resultado
- [ ] T015 [US2] [A3] Crear `consumer/app/reprocess.py` hasta que T014 pase (según [contracts/reprocess.md](contracts/reprocess.md)): recorre `reprocessed_at IS NULL` en `core` y `replay`, reconstruye el mensaje, aplica `rules.evaluate`, escribe en una transacción por fila con el `search_path` del topic; `--dry-run`; resumen y código de salida; `python -m app.reprocess`
- [ ] T016 [US2] [A3] Añadir a `compose.yaml` el servicio `quality-reprocess` (perfil `tools`, imagen del consumidor, `entrypoint` `python -m app.reprocess`, variables de base de datos y Kafka como el consumidor, `restart: "no"`, dependencia de `postgres` sano) y comprobar `docker compose config --services` (siguen cinco) y `docker compose build quality-reprocess`

---

## Phase 5: US5 · Sintéticos (P2)

- [ ] T017 [P] [US5] [A3] Crear `tests/synthetic/__init__.py` y `tests/synthetic/cases.py`: una lista de casos, cada uno con `case` (identificador corto), `event_id = synthetic-<caso>`, mensaje, destino esperado (cuarentena con códigos / exclusión / evento con marcas y país) y descripción; cubrir cada regla de [contracts/rules-catalog.md](contracts/rules-catalog.md) y las cuatro pruebas de aceptación del enunciado (magnitud nula, coordenadas inválidas, evento marítimo, reinicio con lote de 1.000 válidos generados por una función); prueba unitaria `tests/unit/test_synthetic_cases.py` que pasa cada caso por `rules.evaluate` y comprueba el destino esperado
- [ ] T018 [US5] [A3] Crear `tests/synthetic/inject.py` (`python -m tests.synthetic.inject [--list] [--batch N]`): publica los casos al topic en vivo con `synthetic: true` y `synthetic_case`, omite los que ya constan en la base (cuarentena por `payload->>'synthetic_case'`, historial o exclusiones por el prefijo), y `--batch N` publica el lote de reinicio; prueba en `tests/db/test_synthetic.py`: inyectar dos veces no aumenta ningún recuento; todo lo generado queda marcado (`is_synthetic`, marca `synthetic`, prefijo) y las consultas reales no lo devuelven; un evento real nunca aparece como sintético

---

## Phase 6: US4 · Recuentos (P2)

- [ ] T019 [P] [US4] [A4] Crear `db/queries/quality.sql` con consultas con nombre (`-- name: ...`) según [research.md](research.md) R12 y [data-model.md](data-model.md) §6: recibidos por resultado (solo `attempt = 0`), reprocesados aparte, cuarentena por motivo (`unnest(reason_codes)`) y mensajes rechazados distintos, eventos por marca, nulos y porcentaje de magnitud, tipo de magnitud, profundidad, lugar y país sobre terremotos actuales, versiones distintas frente a mensajes, duplicados de versión (debe dar 0), unicidad del estado actual, coordenadas válidas, coherencia `updated ≥ time`, entidades de país existentes, retrasos (ocurrencia → actualización y ocurrencia → ingesta, mediana y percentil 95), y la variante «solo sintéticos» de las principales; todas excluyen lo sintético por defecto
- [ ] T020 [US4] [A4] Montar `./db/queries` en `/queries` (solo lectura) en el servicio `postgres` de `compose.yaml` y crear `tests/db/test_quality_queries.py`: ejecutar el fichero completo contra datos conocidos (un conjunto de mensajes con resultados conocidos) y comprobar cada recuento, que un mensaje con dos motivos cuenta una vez como rechazado y dos en motivos, que recibidos = nuevos + revisados + atrasados + repetidos + excluidos + rechazados con diferencia 0, y que lo sintético queda fuera

---

## Phase 7: Sistema real

> Las ejecuta el orquestador, una a una (tocan el sistema y la base real).

- [ ] T021 [A0] Aplicar `041` a la base existente sin recrearla (`MSYS_NO_PATHCONV=1 docker compose exec postgres sh -c '… /sql/apply.sh "$POSTGRES_DB" 041_consumer_quality.sql'`), dos veces seguidas, y comprobar columnas y clave; reconstruir y reiniciar el consumidor; confirmar `docker compose ps` con cinco servicios sanos. Anotar los recuentos de partida (cuarentena, eventos, marcas, `message_log`) para el «antes»
- [ ] T022 [A0] V2: inyectar los casos sintéticos con el sistema real y comprobar los cinco resultados de la tabla del quickstart; repetir la inyección y comprobar que no cambia nada; guardar en `docs/evidence/004/acceptance.md`
- [ ] T023 [A0] V4: `quality-reprocess --dry-run`, ejecutar, repetir; comprobar las 2 filas reales (recuperadas), las sintéticas y la idempotencia; guardar en `docs/evidence/004/reprocess.md`. **Cuenta el antes y el después** de eventos actuales y de cuarentena
- [ ] T024 [A0] V3: publicar un lote de 1.000 mensajes sintéticos válidos, reiniciar el consumidor a mitad y comparar con una ejecución sin reinicio; guardar en `docs/evidence/004/restart.md`
- [ ] T025 [A0] V5 y V6: país (ejecución de las pruebas y consulta de eventos sin país y con `ambiguous_country`, con el antes/después del cambio de regla) y recuentos (`quality.sql`); guardar en `docs/evidence/004/spatial-and-counts.md`

---

## Phase 8: US6 · Calidad en la memoria (P2)

- [ ] T026 [A0] Ampliar `docs/report.md` con «Calidad de los datos»: fuente, periodo y conjunto analizado (mensajes, versiones distintas, terremotos actuales, sin sintéticos); una tabla por dimensión (completitud, unicidad, validez, consistencia, actualidad, exactitud) con comprobación, consulta, denominador, resultado, acción y limitación; antes/después donde hay tratamiento (magnitud nula, rango, reprocesado, país, profundidad negativa); la explicación de cada decisión (no cero, no rechazar la magnitud negativa, no rechazar antiguos); la regla de frontera y el aviso cartográfico; la nota de no sumar incidencias solapadas; y los casos sintéticos por separado. Actualizar el diccionario con las tres columnas nuevas y el resultado `excluded`; `pytest tests/db/test_data_dictionary.py` debe pasar
- [ ] T027 [A0] Ampliar `README.md` (reprocesado, sintéticos, qué hace cada regla y dónde está el catálogo) y `db/seeds/README.md` si procede; ejecutar V8 repitiendo cada consulta de la memoria y guardar en `docs/evidence/004/quality-queries.md`

---

## Phase 9: Cierre

- [ ] T028 [A0] V9: `pytest tests/db tests/unit tests/contract -v` completo, salida en `docs/evidence/004/tests.txt`; comprobar `git diff 003-usgs-ingestion --stat -- producer api frontend common` vacío
- [ ] T029 [A0] Completar `docs/evidence/004/README.md` con la tabla de V1 a V9 y la revisión constitucional (principios II, III, IV, VI, VII, IX e idioma; el III queda cerrado), ejecutar `scan-evidence.sh` y revisar `git status` antes del commit final

---

## Orquestación

| Agente | Modelo | Tareas | Ficheros que puede tocar | No debe tocar |
|---|---|---|---|---|
| A0 (orquestador, esta sesión) | Sonnet | T001–T005, T021–T029 | `db/sql/`, `compose.yaml` (solo T020/T016 los hacen A3/A4), `docs/`, `README.md`, specs | — |
| A1 | Sonnet | T006–T010 | `consumer/app/rules.py`, `quality.py` (borrar), `persistence.py`, `main.py`, `tests/unit/test_rules*.py`, `tests/db/test_consumer_rules.py`, `test_consumer_persistence.py` | `spatial.py`, `reprocess.py`, `db/` |
| A2 | Sonnet | T011–T013 | `consumer/app/spatial.py`, `tests/unit/test_spatial.py`, la función de país de `test_consumer_rules.py` | `rules.py`, `persistence.py`, `main.py` salvo la llamada a `verify_against_dimension` |
| A3 | Sonnet | T014–T018 | `consumer/app/reprocess.py`, `tests/synthetic/`, `tests/db/test_reprocess.py`, `test_synthetic.py`, `compose.yaml` (solo el servicio nuevo) | `rules.py` (solo lo importa) |
| A4 | Haiku | T019–T020 | `db/queries/quality.sql`, `tests/db/test_quality_queries.py`, `compose.yaml` (solo el montaje) | Todo lo demás |

**Orden**: A0 termina la fase 1 → A1 y A2 en paralelo (ficheros distintos) → A3 cuando A1 ha
terminado (usa `rules.py`) → A4 en paralelo con A3 → A0 hace la fase 7 en serie. **Pruebas de base
de datos**: nunca dos agentes a la vez; A1, A2, A3 y A4 corren solo sus ficheros y A0 serializa.

## Dependencies & Execution Order

```text
Fase 1 (A0) ─┬→ A1 (T006–T010) ─┬→ A3 (T014–T018) ─┐
             ├→ A2 (T011–T013) ─┘                  ├→ Fase 7 (A0) → Fase 8 → Fase 9
             └→ A4 (T019–T020) ────────────────────┘
```

## Implementation Strategy

**MVP**: fases 1 y 2 (reglas nuevas con la magnitud nula conservada). Después país, reprocesado,
sintéticos, recuentos, sistema real y memoria. El commit se hace al terminar cada fase.

## Notes

- Las 2 filas reales de cuarentena (`magnitude_out_of_range`) son el primer caso real del
  reprocesado y el «antes/después» de la memoria.
- T012 y T008 comparten una interfaz (`lookup` después de `evaluate`): A0 la fija antes de lanzar
  A1 y A2 en el prompt de cada agente.
- La rama no se fusiona en `main` hasta cerrar las desviaciones abiertas del principio VIII.
