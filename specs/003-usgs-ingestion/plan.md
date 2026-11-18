# Implementation Plan: Ingesta desde USGS

**Branch**: `003-usgs-ingestion` | **Date**: 2026-11-15 | **Spec**: `spec.md`

**Input**: Feature specification from `/specs/003-usgs-ingestion/spec.md`

## Summary

Hacer que la ingesta deje rastro completo y cargar el histórico. El productor pasa a registrar
cada consulta al feed en `core.extraction`, a guardar el original una vez por huella en
`core.raw_payload`, a conservar las exclusiones, a usar peticiones condicionales, a purgar los
originales cada 24 horas y a avisar de los huecos al arrancar. Un programa nuevo,
`catalog-loader`, lanzado a mano dentro de la red de Compose, carga el catálogo por meses
(2025 obligatorio, 2026 como ampliación y los huecos tras una parada), sin truncar nunca,
guardando los ficheros en `data/` y publicando por `earthquakes.catalog`.

No cambia el modelo de datos de la spec 002 ni el consumidor: todo lo que la ingesta necesita
ya existe (ver [research.md](research.md) R15). El comportamiento de USGS en el que se apoya el
diseño se comprobó con peticiones reales el 2026-11-15: 18.302 terremotos en 2025 con magnitud
≥ 4, ningún mes por encima del máximo, error 400 en lugar de truncado, límites `[inicio, fin)`
y `If-Modified-Since` admitido.

## Technical Context

**Language/Version**: Python 3.11 (imagen `python:3.11.10-slim-bookworm`); SQL de PostgreSQL 16

**Primary Dependencies**: las ya fijadas en la spec 002: aiokafka 0.12.0, asyncpg 0.30.0 y
requests 2.32.3 en el productor. No se añade ninguna biblioteca

**Storage**: PostgreSQL 16.4, esquema `core` (`extraction`, `raw_payload`, `excluded_event`,
`publish_state`); Kafka (`earthquakes.live`, `earthquakes.catalog`); ficheros en
`data/usgs/catalog/`, fuera de Git

**Testing**: pytest en el contenedor `tests` (`compose.dev.yaml`) contra `observatory_test`;
fuente simulada con la biblioteca estándar; escenarios con el sistema real en
[quickstart.md](quickstart.md)

**Target Platform**: Docker Engine 26+ con Compose v2; Windows 11 (Git Bash) y Linux

**Project Type**: sistema de datos con varios servicios (pipeline en streaming, API y SPA)

**Performance Goals**: una consulta al feed por intervalo (60 s) con ciclo completo en menos de
5 s en condiciones normales; carga de 2025 (18.302 eventos, 12 descargas) en menos de 15 minutos

**Constraints**: sin cambios en el modelo, el consumidor, la API ni el panel; no consultar la
fuente con más frecuencia que la configurada; respetar `Retry-After`; nada de datos descargados
en Git; cinco servicios en el arranque normal; código en inglés y documentación en español

**Scale/Scope**: 1.440 extracciones al día y hasta unos 175 MB de originales retenidos (7 días);
18.302 eventos de 2025 y unos 14.200 de 2026; unos 300 eventos al día de todas las magnitudes en
una recuperación de huecos

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación previa | Evaluación tras el diseño |
|---|---|---|
| I. Arquitectura reproducible y superficie mínima | Cumple: no se añade ningún servicio al arranque; la carga es una herramienta bajo perfil | Cumple: `docker compose up --build -d` sigue levantando cinco servicios; sin puertos nuevos; sin dependencias nuevas |
| II. Al menos una vez, idempotente y versionada | Cumple: se mantiene clave = `event_id` y marca tras la confirmación | Cumple: feed y catálogo comparten `publish_state`; repetir la carga no publica nada (R6) |
| III. Calidad: conservar, señalar o cuarentena | Cumple en lo que toca a la ingesta: los tipos distintos de terremoto se conservan con motivo | Cumple: exclusiones con motivo y extracción; elementos no identificables contados y localizables (R5). Sigue abierta la desviación del consumidor con la magnitud nula (spec 004) |
| IV. Integración espacial | No afectado | No afectado |
| V. Original y procedencia | Es el objetivo: hoy no se cumple | **Cumple y cierra la desviación de la spec 002**: original antes de transformar, una copia por contenido, retención de 7 días aplicada, toda consulta registrada, subdivisión sin truncar, deduplicación, nada se borra, descargas fuera de Git con procedimiento de regeneración |
| VI. Aislamiento de la reproducción | Cumple: no se usa el topic ni el esquema de reproducción | Cumple: histórico y huecos van a `core` por `earthquakes.catalog` con `mode = live` |
| VII. Analítica desde el estado actual | No afectado: no se crean contadores | Cumple. Se documenta qué periodos tienen todas las magnitudes y cuáles solo M ≥ 4, para que la comparación use el mismo filtro |
| VIII. Contrato de la API | Fuera de alcance | La ingesta deja disponible `last_ingestion` como exige el contrato; devolverlo es de la spec 006 |
| IX. Evidencia ejecutada | Cumple: pruebas de comportamiento y escenarios con el sistema real | Cumple: fuente simulada para los fallos, mediciones reales de la fuente y evidencia en `docs/evidence/003/` |
| Idioma y repositorio público | Cumple | Cumple: identificadores en inglés, documentos en español, agente de usuario sin datos personales, `data/` ignorado |

Sin violaciones. No hay entradas en *Complexity Tracking*.

**Desviaciones temporales que siguen abiertas** (ninguna la introduce esta funcionalidad):

| Principio | Qué sigue sin cumplirse | La cierra |
|---|---|---|
| III | El consumidor envía la magnitud nula a cuarentena y rechaza la negativa. Afecta a eventos pequeños recuperados en un hueco; no a 2025 ni a 2026 (M ≥ 4) | spec 004 |
| VIII | La API no devuelve aún el formato del contrato ni `last_ingestion` desde las extracciones | spec 006 |

Mientras existan, la rama no se fusiona en `main`.

## Project Structure

### Documentation (this feature)

```text
specs/003-usgs-ingestion/
├── plan.md              # Este fichero
├── research.md          # Hechos observados en USGS y decisiones
├── data-model.md        # Qué escribe la ingesta en el modelo de la 002
├── quickstart.md        # Escenarios de validación V1 a V12
├── contracts/
│   ├── catalog-loader.md   # Orden de carga: opciones, salida y códigos
│   ├── messages.md         # Mensajes publicados en Kafka
│   └── runtime.md          # Servicios y variables: cambios sobre la 002
├── checklists/
│   └── requirements.md
└── tasks.md             # Lo genera /speckit-tasks
```

### Source Code (repository root)

```text
compose.yaml                     # AÑADIR servicio catalog-loader (perfil tools); variables nuevas del productor
compose.dev.yaml                 # AÑADIR servicio usgs-stub (perfil test)
.env.example                     # AÑADIR variables de contracts/runtime.md

common/
└── settings.py                  # AMPLIAR: variables de USGS, margen de huecos, DATA_DIR

producer/app/
├── usgs.py                      # NUEVO: cliente HTTP con reintentos, Retry-After y resultado estructurado
├── fingerprint.py               # NUEVO: huella canónica de la colección y de ficheros
├── classify.py                  # NUEVO: terremoto, excluido o no identificable
├── provenance.py                # NUEVO: escrituras en extraction, raw_payload y excluded_event
├── publisher.py                 # NUEVO: construir el mensaje, enviar, confirmar y marcar (feed y catálogo)
├── gaps.py                      # NUEVO: cálculo de huecos y de su cobertura desde extraction
├── catalog.py                   # NUEVO: recuento, descarga, planificación y subdivisión de intervalos
├── catalog_load.py              # NUEVO: orden de carga (argumentos, resumen, códigos de salida)
├── main.py                      # REHACER el ciclo: condicional, registro, exclusiones, purga, aviso de hueco
├── persistence.py               # SE MANTIENE (publish_state)
├── config.py                    # SE MANTIENE
├── feed.py                      # ELIMINAR: lo sustituye usgs.py
├── history.py                   # ELIMINAR: lo sustituye catalog_load.py (escribía en db/seeds)
└── replay.py                    # NO SE TOCA (spec 005)

tests/
├── support/
│   └── usgs_stub.py             # NUEVO: fuente simulada con guion de respuestas
├── unit/
│   ├── test_usgs_client.py      # NUEVO: reintentos, Retry-After, tiempo agotado, clasificación de resultados
│   ├── test_fingerprint.py      # NUEVO
│   ├── test_classify.py         # NUEVO
│   ├── test_catalog_plan.py     # NUEVO: meses, subdivisión, intervalo imposible
│   ├── test_gaps.py             # NUEVO: detección y cobertura
│   ├── test_catalog_load_cli.py # NUEVO: argumentos y códigos de salida
│   ├── test_feed.py             # ELIMINAR (prueba feed.py)
│   └── test_history.py          # ADAPTAR: conserva solo lo que prueba replay.py
├── db/
│   ├── test_feed_cycle.py       # NUEVO: ciclo completo contra la base real con fuente y broker simulados
│   ├── test_feed_failures.py    # NUEVO: cada tipo de fallo
│   ├── test_catalog_load.py     # NUEVO: carga, repetición, reanudación, deduplicación
│   └── test_purge_cycle.py      # NUEVO
└── analysis/
    └── source_profile.py        # NUEVO: perfil de la respuesta de la fuente

docs/
├── report.md                    # AMPLIAR: fuentes y extracción, procedencia, retención, fallos, huecos
└── evidence/003/                # NUEVO: resultados de quickstart.md

README.md                        # AMPLIAR: carga histórica, ampliación a 2026, huecos, datos en data/
db/seeds/README.md               # ACTUALIZAR la referencia al procedimiento de descarga
```

**Ficheros que se eliminan**: `producer/app/feed.py`, `producer/app/history.py` y
`tests/unit/test_feed.py`.

**No se toca**: `db/sql/`, `consumer/`, `api/`, `frontend/` ni `producer/app/replay.py`.

**Structure Decision**: se mantiene la estructura por servicio de la spec 002. La carga del
catálogo vive en el paquete del productor porque comparte con el feed el cliente HTTP, la
clasificación, el registro de procedencia y la publicación; así ambos caminos aplican
exactamente las mismas reglas. No se crea una imagen nueva: `catalog-loader` usa la del
productor con otro punto de entrada.

## Orden de implementación

1. **Base común**: configuración, cliente HTTP, huella, clasificación y fuente simulada, con sus
   pruebas unitarias (US3 en lo que toca al cliente).
2. **Feed con procedencia** (US1): registro de extracciones, originales, exclusiones,
   publicación y petición condicional; ciclo nuevo del productor; salud. V1, V2, V11.
3. **Fallos de la fuente** (US3): los cinco casos de extremo a extremo. V3.
4. **Carga del catálogo** (US2): planificación por meses, subdivisión, descarga, ficheros,
   publicación, resumen y servicio de Compose. V4, V5, V6.
5. **Huecos** (US4): cálculo desde las extracciones, aviso al arrancar, `--gaps` y propósito
   `gap_recovery`. V8.
6. **Retención** (US5): purga periódica. V9.
7. **Ampliación con 2026** (US6): ejecución y comprobación. V7.
8. **Documentación y evidencias**: perfil de la fuente, memoria, README, V10 y V12.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| USGS cambia recuentos durante la carga (catálogo vivo) | Recuento previo por intervalo, comprobación de que se recibe lo declarado, recuento final del periodo y código de salida 3 si la diferencia no es cero |
| Permisos de escritura en `./data` en Linux | `LOADER_UID` y `LOADER_GID`; comprobarlo en el equipo Linux antes de cerrar la tarea (R9) |
| La fuente limita por exceso de peticiones | Una consulta por intervalo, `If-Modified-Since`, reintentos acotados, `Retry-After` respetado, agente de usuario identificable |
| Las pruebas dependen de Internet | Todos los fallos y la lógica se prueban con la fuente simulada; solo los escenarios de evidencia usan USGS |
| El ciclo nuevo del productor altera la continuidad lograda en la 002 | Las pruebas de la 002 siguen en verde (V12) y el escenario V8 de la 002 (reinicio sin republicar) se repite |
| 18.302 mensajes de golpe retrasan al consumidor | Es una carga única; el consumidor procesa unos 100 mensajes por segundo y la validación espera a que termine antes de contar |
| Los originales crecen más de lo estimado | Retención de 7 días aplicada y medida en V9; el tamaño real se anota en la memoria |
| Eventos pequeños de un hueco acaban en cuarentena por la regla heredada de magnitud nula | Documentado como desviación; no se pierden y se reprocesan con la spec 004 |

## Complexity Tracking

Sin violaciones de la constitución que justificar.
