# Evidencia de la spec 005 · Reproducción acelerada de una selección histórica

**Fecha**: 2026-11-16 · **Rama**: `005-historical-replay` · Entorno y límites:
[00-environment.md](00-environment.md) · Guía de los escenarios:
[quickstart.md](../../../specs/005-historical-replay/quickstart.md).

Todos los escenarios se ejecutaron con el sistema real (Compose, Kafka, PostgreSQL y el consumidor de
las specs 002 a 004); cada uno guarda lo esperado, lo observado y la salida.

## Índice de escenarios

| Escenario | Qué demuestra | Resumen | Resultado |
|---|---|---|---|
| [V1 · selección](v1-selection.md) | FR-001 a FR-004 | 5.301 eventos seleccionados del catálogo ya descargado y registrados; rechazo de periodo sin cobertura, de magnitud insuficiente y de fichero alterado; selección vacía | ✔ |
| [V2 · 5.301 eventos acelerados](v2-replay-5000.md) | FR-005 a FR-007, FR-011, FR-014, SC-002, SC-004 | 196,8 eventos/s (objetivo 200), 5.301 en `replay`, 0 tiempos alterados, `replayed_at` informado | ✔ |
| [V3 · aislamiento](v3-isolation.md) | FR-013, SC-003 | recuento y suma de las 10 tablas de `core` idénticos tras cada escenario | ✔ |
| [V4 · control](v4-control.md) | FR-008 a FR-010, SC-008 | pausa en 0,41 s, reanudar sin saltos, detener, un solo `start` activo | ✔ |
| [V5 · repetición tras `reset`](v5-repeat.md) | FR-009, SC-007 | huella idéntica a la primera ejecución | ✔ |
| [V6 · casos sintéticos](v6-synthetic.md) | FR-016 a FR-018, SC-005 | `new` 3, `duplicate` 1, `revised` 1, `stale` 1, `quarantined` 1 | ✔ |
| [V7 · reinicio del consumidor](v7-consumer-restart.md) | SC-006 | huella idéntica, sin duplicados de efecto | ✔ |
| V8 · identificabilidad y mismo identificador | FR-012, FR-014 | incluido en [V2](v2-replay-5000.md) | ✔ |
| [V9 · repositorio y material heredado](v9-repository.md) | FR-019 | sin conjuntos descargados en Git; destino de cada lote heredado | ✔ |

## Pruebas automáticas

[tests.txt](tests.txt): **682 pruebas pasan** (699 tras la corrección del hallazgo 2) en el contenedor `tests` (`pytest tests`), incluidas las
anteriores de las specs 002 a 004 (sin regresiones) y las nuevas de esta spec:

| Fichero | Comprueba |
|---|---|
| `tests/unit/test_replay_pacing.py`, `…_message.py`, `…_control.py`, `…_selection.py`, `…_runner.py`, `…_cli.py`, `…_synthetic.py` | cadencia, mensaje (tiempos originales, clave, modo), ficheros de control, filtros de la selección, publicación con pausa y parada, códigos de salida, casos sintéticos |
| `tests/unit/test_replay_service_layout.py` | que el paquete se importa con la disposición de la imagen (detecta el fallo de importación hallado en V1) |
| `tests/db/test_replay_replayed_at.py` | `replayed_at` del mensaje llega a `replay.event_current` (cambio mínimo del consumidor) |
| `tests/db/test_replay_selection.py` | registro en `core.extraction`, rechazos por huella, cobertura y magnitud |
| `tests/db/test_replay_isolation_check.py` | la comparación detecta filas alteradas, insertadas y borradas |
| `tests/db/test_replay_end_to_end.py` | selección → publicación → consumidor real; `core` intacto; mismo identificador con valores distintos |
| `tests/db/test_replay_lock.py` | una sola reproducción activa; `reset` sin efecto en `core` |
| `tests/db/test_replay_control_flow.py` | pausa, parada y repetición tras `reset` con la base real |
| `tests/db/test_replay_synthetic.py` | los siete mensajes sintéticos con el resultado esperado |
| `tests/db/test_replay_consumer_restart.py` | reinicio del consumidor con relectura solapada |

## Linux

**Linux (2026-11-17)**: la suite completa (`pytest tests`) pasó en un equipo Linux: **886 pruebas en verde** ([linux-g3.md](../008/linux-g3.md)). No se repitieron los escenarios con el sistema real en Linux.

## Revisión contra la constitución

| Principio | Revisión |
|---|---|
| II. Al menos una vez, idempotente | El productor espera la confirmación de cada mensaje y se detiene si Kafka falla. Repetir un mensaje da `duplicate`; el reinicio del consumidor no duplica efectos (V7 y su prueba con relectura). |
| III. Calidad | Se reproduce lo seleccionado sin filtrar anomalías; el consumidor aplica las reglas de la spec 004 (la cuarentena sintética lo demuestra). Las magnitudes nulas no cumplen un filtro de magnitud mínima y se cuentan en la selección. |
| V. Original y procedencia | La selección sale de lo descargado, se verifica contra la huella de `core.raw_payload` y queda registrada en `core.extraction`. Ningún conjunto en Git (V9). |
| VI. Aislamiento de la reproducción | Topic propio, esquema `replay`, mismo código del consumidor, tiempo original intacto y `replayed_at` añadido, `core` idéntico tras cada escenario, `replay.reset()` sin equivalente en `core`. El etiquetado «REPRODUCCIÓN» queda para las specs 006 y 007. |
| VII. Analítica desde el estado actual | Todos los recuentos salen de SQL sobre las tablas; no hay contadores incrementales. |

**Única excepción justificada**: la selección escribe una fila en `core.extraction` (propósito
`replay_selection`, previsto por el modelo). La comprobación de aislamiento la excluye y la cuenta
aparte.

## Hallazgos de la verificación

1. **Fallo de importación en la imagen** (corregido): `selection.py` usaba `producer.app…`, ruta
   que solo existe en las pruebas; la imagen del productor tiene el paquete `app`. Detectado en V1;
   corregido con imports relativos y protegido con `test_replay_service_layout.py`.
2. **Defecto de la spec 004 solo en Windows** (corregido después de la verificación; ajeno a la
   reproducción): `datetime.fromtimestamp()` lanza `OSError` con instantes anteriores a 1970 en Windows,
   y las reglas del consumidor lo convertían en el motivo `invalid_time` para un instante válido aunque
   antiguo (1881 en el caso sintético `model_constraint_violation`). Ahora `consumer/app/rules.py`,
   `producer/app/classify.py` y `producer/app/replay/cli.py` suman milisegundos a la época, con el mismo
   resultado en cualquier sistema, y `tests/unit/test_pre_1970_instants.py` lo protege. Tras el cambio:
   402 pruebas unitarias en Windows y 699 en total en el contenedor Linux. Las imágenes en ejecución
   durante la verificación no incluían esta corrección.
3. **`replay compare` imprime solo el veredicto**, no el recuento por tabla; la tabla de V3 sale de la
   instantánea guardada (`data/replay/core-snapshot.json`). Mejora posible, no necesaria para los
   requisitos.
