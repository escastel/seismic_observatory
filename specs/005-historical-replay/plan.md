# Implementation Plan: Reproducción acelerada de una selección histórica

**Branch**: `005-historical-replay` | **Date**: 2026-11-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-historical-replay/spec.md`

## Summary

Una orden nueva, `replay`, que vive en el servicio del productor (perfil `tools`, como
`catalog-loader`), selecciona eventos de los ficheros ya descargados en `data/usgs/catalog/`,
registra la selección en `core.extraction` con propósito `replay_selection` y los publica en
`earthquakes.replay` con modo `replay`, clave igual al identificador, tiempo original intacto y
`replayed_at`. El consumidor existente los escribe en el esquema `replay` sin bifurcar su código.
La orden se controla (pausar, reanudar, detener) mediante un fichero de control en `data/replay/`,
garantiza una sola reproducción activa con un bloqueo asesor de PostgreSQL y repite desde cero con
`replay.reset()`. Un conjunto sintético fijo (5 casos, 7 mensajes) demuestra primera versión,
repetición exacta, revisión, versión antigua tardía y cuarentena. Una comprobación de aislamiento
compara recuento y suma de comprobación de todas las tablas de `core` antes y después.

El modelo de las specs 002 a 004 **no cambia**. El consumidor recibe un único ajuste mínimo y
justificado (R1): respetar el `replayed_at` que trae el mensaje en lugar de asignar la hora de
lectura. `producer/app/replay.py` se sustituye por un paquete; los lotes `db/seeds/historical_*`
dejan de versionarse (R9).

## Technical Context

**Language/Version**: Python 3.11 (imágenes del productor y del consumidor); SQL de PostgreSQL 16

**Primary Dependencies**: las ya fijadas (aiokafka 0.12.0, asyncpg 0.30.0). Sin dependencias nuevas

**Storage**: PostgreSQL 16.4, esquemas `core` y `replay` sin cambios; ficheros de control y estado
en `data/replay/` (ignorado por Git)

**Testing**: pytest en el contenedor `tests`; pruebas de comportamiento con Kafka simulado
(`tests/support/fake_kafka.py`) y base real, y verificación final con el sistema real mediante la
skill `verify-stack`

**Target Platform**: Docker Engine 26+ con Compose v2; Windows 11 (Git Bash) y Linux

**Project Type**: sistema de datos con varios servicios; la orden es una herramienta CLI

**Performance Goals**: 5.000 eventos a 200 eventos/s en menos de 60 s con el consumidor al día
(el consumidor mantiene unos 700 mensajes/s); pausa efectiva en menos de 2 s

**Constraints**: cinco servicios en el arranque normal (el servicio `replay` va en el perfil
`tools`); sin tocar API, panel ni modelo; sin datos en Git; código en inglés y documentación en
español; LF y `python3` en `.specify/`

**Scale/Scope**: catálogo 2025 con magnitud ≥ 4 (unos 17.000 eventos en 28 ficheros mensuales);
selecciones previstas de 5.000 a 17.000 eventos

## Constitution Check

| Principio | Evaluación previa | Evaluación tras el diseño |
|---|---|---|
| I. Arquitectura reproducible | Cumple: no se añade servicio al arranque | Cumple: `replay` solo en perfil `tools`, sin puertos, con las dependencias ya fijadas |
| II. Al menos una vez, idempotente | Cumple: el consumidor no cambia de reglas | Cumple: el productor espera la confirmación de cada mensaje; repetir una reproducción sin reiniciar da `duplicate`; reiniciar el consumidor no duplica efectos |
| III. Calidad | No afectado | Cumple: se reproduce todo lo seleccionado, incluidas magnitudes nulas; el filtro `min_mag` deja fuera las nulas y se cuentan en la selección; los sintéticos incluyen un caso de cuarentena |
| IV. Integración espacial | No afectado | Cumple: el país de cada evento lo asigna el consumidor igual que en `core`; la zona de la selección es un recuadro geográfico, sin atribuir país por texto |
| V. Original y procedencia | Cumple: la selección sale de lo descargado | Cumple: la selección se registra en `core.extraction` y verifica la huella de cada fichero contra `core.raw_payload`; ningún conjunto en Git |
| VI. Aislamiento de la reproducción | **Es el objetivo** | Cumple: topic propio, esquema `replay`, mismo código del consumidor, tiempo original conservado, `replayed_at` añadido, comprobación de recuentos y sumas de `core`, reinicio con `replay.reset()` sin equivalente en `core` |
| VII. Analítica desde el estado actual | No afectado | Cumple: sin contadores; todo recuento sale de SQL |
| VIII. Contrato de la API | Fuera de alcance | Sin cambios; el etiquetado «REPRODUCCIÓN» queda para la 006 y 007 |
| IX. Evidencia ejecutada | Cumple | Cumple: escenarios V1 a V9 de [quickstart.md](quickstart.md) con evidencia en `docs/evidence/005/` |
| Idioma y repositorio público | Cumple | Cumple: identificadores en inglés, documentación en español, `data/replay/` ignorado |

**Excepción justificada (única)**: el registro de la selección escribe una fila en
`core.extraction`. Es provenance (el modelo ya prevé el propósito `replay_selection`), no un dato
de eventos, pero altera `core`. La comprobación de aislamiento excluye de esa tabla solo las filas
con ese propósito y compara todo lo demás (R5).

**Cambio mínimo en la spec 004**: una línea en el consumidor (R1). No altera reglas, resultados ni
el modelo; se prueba con las pruebas existentes más una nueva.

## Project Structure

### Documentation (this feature)

```text
specs/005-historical-replay/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── replay-cli.md          # órdenes, opciones, códigos de salida
│   ├── replay-message.md      # mensaje publicado en el topic de reproducción
│   ├── synthetic-cases.md     # cinco casos, resultado esperado y consultas
│   └── isolation-check.md     # instantánea y comparación de core
├── checklists/requirements.md
└── tasks.md                   # lo genera /speckit-tasks
```

### Source Code (repository root)

```text
producer/app/
├── replay/                    # sustituye a replay.py
│   ├── __init__.py
│   ├── __main__.py            # python -m app.replay
│   ├── cli.py                 # subórdenes: select, start, pause, resume, stop, status, reset, snapshot, compare
│   ├── selection.py           # lectura de ficheros, verificación, filtros, orden, registro en core.extraction
│   ├── pacing.py              # cálculo de la cadencia (eventos/s y factor de aceleración)
│   ├── runner.py              # publicación, pausa, parada, bloqueo asesor
│   ├── control.py             # fichero de control y de estado en data/replay/
│   ├── message.py             # construcción del mensaje de reproducción
│   ├── synthetic.py           # los cinco casos sintéticos, fechas fijas
│   └── isolation.py           # instantánea y comparación de las tablas de core
consumer/app/main.py           # un ajuste: usa replayed_at del mensaje (R1)
compose.yaml                   # servicio replay (perfil tools)
.env.example                   # REPLAY_DEFAULT_RATE (opcional)
db/seeds/                      # se retiran historical_1900.jsonl y historical_2025.jsonl
tests/
├── unit/                      # pacing, selección, control
├── db/                        # selección registrada, aislamiento, sintéticos, bloqueo único
└── integration/               # reproducción de 5.000 eventos con el sistema real
docs/evidence/005/
docs/report.md                 # apartado nuevo
README.md                      # demostración paso a paso
```

**Structure Decision**: se amplía el servicio `producer` (misma imagen, mismo código de
configuración, conexión y Kafka) con un paquete en lugar de crear un servicio nuevo con imagen
propia; evita duplicar dependencias y respeta el límite de infraestructura. Las pruebas siguen la
organización de `tests/` de las specs anteriores.

## Complexity Tracking

Sin violaciones constitucionales abiertas. Dos puntos de coste deliberado, ambos justificados en
[research.md](research.md): el bloqueo asesor de PostgreSQL (R4, evita una tabla nueva) y el
fichero de control (R3, evita un servicio nuevo con API).
