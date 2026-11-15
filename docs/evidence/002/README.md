# Evidencias de la spec 002: plataforma y modelo de datos

Resultados de los escenarios de [quickstart.md](../../../specs/002-platform-data-model/quickstart.md),
observados entre el 2026-11-15T00:15Z y el 2026-11-15T01:20Z en Windows 11 Pro for Workstations
con Docker Desktop 29.1.3 (motor con 12 CPU y 7,6 GiB). Ningún escenario se marca como superado
sin haberlo ejecutado; cada fichero enlazado incluye la orden, la cabecera de equipo y commit, y
la salida.

| Escenario | Esperado | Observado | Resultado | Evidencia |
|---|---|---|---|---|
| V1 | Cinco servicios sanos en menos de 3 min, sin `tunnel`; diez arranques desde cero | 10 arranques entre 15,2 y 22,4 s (mediana 15,7 s); `tunnel` solo con su perfil | SUPERADA | [cold-starts.md](cold-starts.md), [startup.md](startup.md) |
| V2 | Solo `api` publica puerto, en `127.0.0.1:8000`; 5432, 9092 y 8000 cerrados desde otro dispositivo | Solo `api 127.0.0.1:8000`; desde la IP de red local del propio equipo, todos cerrados | SUPERADA en el equipo; **pendiente** la prueba desde otro dispositivo | [startup.md](startup.md) |
| V3 | Tablas en `core` y `replay`, 177 países, 49.673 días | 10 tablas en `core`, 6 en `replay`, 177 países, 1900-01-01 a 2035-12-31 sin huecos | SUPERADA | [model-structure.md](model-structure.md) |
| V4 | FAQ 12: `new`, `duplicate`, `revised`, `duplicate`, `new`; 2 eventos, 3 versiones, 5 mensajes; nulos, profundidad negativa, sin país y rangos | Igual; `tests/db/test_event_versions.py`, `test_event_constraints.py`, `test_provenance.py` en verde | SUPERADA | [db-tests.txt](db-tests.txt) |
| V5 | 1.000 pasadas no cambian ningún recuento | 30 eventos, 40 versiones, 5 rechazos y 50 mensajes tras la 1.ª y la 1.000.ª pasada | SUPERADA | [db-tests.txt](db-tests.txt) |
| V6 | 10.000 eventos en `replay` y su vaciado no cambian `core` | Recuento y suma de comprobación de `core` idénticos; dimensiones intactas | SUPERADA | [db-tests.txt](db-tests.txt) |
| V7 | `observatory_reader` no puede borrar | `permission denied for table event_current`; además, `tests/db/test_roles.py` | SUPERADA | [model-structure.md](model-structure.md), [db-tests.txt](db-tests.txt) |
| V8 | Mismo recuento tras reiniciar; sin republicar; todo lo publicado consta en `message_log` | 193 → 193; «Published 0»; 0 publicados sin mensaje | SUPERADA | [startup.md](startup.md) |
| V9 | Reintentos con espera creciente y recuperación sola; salud degradada durante la caída | Esperas de 1, 2, 4, 8 y 16 s; recuperación sin reiniciar; `degraded` y luego `ok` | SUPERADA | [startup.md](startup.md) |
| V10 | Con las variables de ngrok, HTTPS responde en `/api/salud` | 200 por HTTPS tras cambiar a `ngrok/ngrok:3.39.13-alpine` (3.18.4 rechazado, ERR_NGROK_121) | SUPERADA | [startup.md](startup.md) |
| V11 | Tabla sin y con índice en tres tamaños; `bench` eliminado | 4 índices secundarios conservados (×2,4 a ×4.936 con 1.000.000 de filas); BRIN solo medido; `bench` eliminado | SUPERADA | [index-benchmark.md](index-benchmark.md) |
| V12 | Ningún fichero versionado de más de 5 MB, ninguna credencial ni `node_modules`; imágenes sin datos | Ninguno de más de 5 MB; «limpio»; ninguna imagen contiene `db/seeds` ni conjuntos de datos | SUPERADA | [repository-hygiene.txt](repository-hygiene.txt) |

Pruebas automáticas: 161 superadas (`tests/db`, `tests/unit`, `tests/contract`), en
[db-tests.txt](db-tests.txt).

## SC-001: arranque por una persona ajena al proyecto (T057)

**NO EJECUTADA.** Requiere que una persona que no conozca el proyecto levante el sistema solo
con el `README.md`. Cuando se haga, anotar aquí el tiempo empleado, las dudas y las correcciones
aplicadas al README.

## Revisión constitucional (v2.1.0, T058)

| Principio | Estado al cerrar la 002 |
|---|---|
| I. Arquitectura reproducible | Cumple: cinco servicios con salud y reintentos, volúmenes, retención de Kafka de 7 días, dependencias fijadas, solo la API publicada y en `127.0.0.1` |
| II. Al menos una vez, idempotente | Cumple: el productor marca tras la confirmación de Kafka con clave `event_id`; offset tras el commit; un grupo nuevo empieza por el principio; reprocesar no cambia recuentos |
| III. Calidad | Cumple en el modelo. Desviación conocida: el consumidor aún rechaza la magnitud nula y negativa (spec 004). Corregido aquí: una versión que el modelo rechaza va a cuarentena (`model_constraint_violation`) en lugar de bloquear el topic |
| V. Original y procedencia | Cumple en el modelo (`extraction`, `raw_payload`, `payload` por versión). Desviación conocida: el productor aún no registra extracciones ni originales (spec 003) |
| VI. Aislamiento de la reproducción | Cumple: esquema `replay`, `replayed_at` obligatorio, `replay.reset()` sin equivalente en `core`, datos de medición en `bench` eliminado |
| VIII. Contrato de la API | Desviación conocida: formato y `last_ingestion` aún no cumplen el contrato (spec 006) |
| IX. Evidencia ejecutada | Cumple: esta tabla, con salida guardada de cada escenario y mediciones en tres tamaños |
| Idioma y repositorio público | Cumple: código e identificadores en inglés, documentación en español; `git status` sin ficheros de datos, `.env` ni credenciales; ninguna evidencia contiene secretos de `.env` (`scan-evidence.sh`) |

Por las tres desviaciones conocidas (III, V, VIII), la rama no se fusiona en `main` hasta las
specs 003, 004 y 006, como fija el plan.
