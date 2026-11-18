---

description: "Task list for feature 008: analysis, performance, costs and deliverables closure"
---

# Tasks: Análisis, rendimiento, costes y cierre de entregables

**Input**: [plan.md](plan.md), `spec.md`, [research.md](research.md),
[data-model.md](data-model.md), [contracts/report-sections.md](contracts/report-sections.md),
[quickstart.md](quickstart.md)

**Tests**: solo para el código de medición nuevo (principio IX, FR-027): pruebas de comportamiento
con pytest (entrada pequeña, salidas coherentes, `bench` no queda detrás), nunca de texto en el
código. El resto son documentos y evidencias, verificados con los escenarios V1–V12.

**Reglas**: código en inglés; documentación en español; LF. Nunca leer ni imprimir `.env`; no
ejecutar `docker compose config`. Sin cambios en `api/` ni `frontend/` (FR-025; solo con necesidad
demostrada y documentada). Ninguna dependencia nueva. Nada de datos ni secretos en Git. Los datos
sintéticos (esquema `bench`) nunca entran en una cifra real. `docker compose down -v` pide
confirmación explícita. Nunca dos ejecuciones de `tests/db` a la vez.

**Agentes** (etiqueta `[A#]`, norma de `CLAUDE.md`):

- `[A0]` sesión principal: todo lo que toca el sistema real (Docker, base, navegador), mediciones,
  cifras, conclusiones, matrices, evidencias, memoria, commit.
- `[A1]` agente nuevo en segundo plano, **Sonnet**: scripts de medición y sus pruebas.
- `[A2]` agente nuevo en segundo plano, **Haiku**: tablas y redacción mecánica a partir de la
  evidencia ya guardada (nunca inventa cifras).

Cada agente recibe un prompt corto que apunta a este fichero (nunca `fork`), solo toca los ficheros
listados en su tarea y no hace commit. Dos agentes a la vez solo si sus ficheros no se solapan.

## Format: `[ID] [P?] [Story] [A#] Descripción con ficheros`

---

## Phase 1: Setup

- [x] T001 [A0] Comprobar rama `008-analysis-costs-deliverables`, `.specify/feature.json` y que el stack arranca (skill `verify-stack`); guardar el estado base (recuentos de `core.event_current`, versión de PostgreSQL, equipo) en `docs/evidence/008/00-environment.md`
- [x] T002 [A0] Leer `docs/evidence/002` a `007` (README de cada una), `docs/report.md` (índice) y los §8, §10, §11, §12 y §13 del enunciado en la carpeta local `resources`; anotar en `docs/evidence/008/00-environment.md` las 11 pruebas de §11 y los entregables de §12

---

## Phase 2: Foundational (bloquea las historias)

- [x] T003 [A0] Decidir R5: mirar `api/` y comprobar si la API puede leer un esquema sintético aislado sin cambiar el contrato; registrar la decisión (con o sin cambio justificado) en `docs/evidence/008/00-environment.md`
- [x] T004 [A0] Fijar el instante de referencia y el formato de cada conclusión (`contracts/report-sections.md`); crear `tests/analysis/queries.sql` vacío con cabecera (solo lectura sobre `core.event_current`)

**Checkpoint**: decisión R5 tomada y entorno documentado.

---

## Phase 3: User Story 1 - Conclusiones fundamentadas (Priority: P1) 🎯 MVP

**Goal**: ≥ 3 conclusiones con cifras regenerables.

**Independent Test**: V1–V4.

- [x] T005 [US1] [A0] Ejecutar contra `core.event_current` las consultas candidatas (reparto por país incluido «Sin país asignado»; últimas 24 h frente a media diaria 2025 con `min_mag=4`; profundidad o magnitud por región; patrón por hora UTC) y guardar las consultas en `tests/analysis/queries.sql` y las salidas con instante en `docs/evidence/008/analysis-queries.md`
- [x] T006 [US1] [A0] Contrastar con `GET /api/estadisticas` las cifras que la API calcula (mismo periodo y filtros) y anotar diferencias en `docs/evidence/008/analysis-api.md`
- [x] T007 [US1] [A0] Elegir ≥ 3 conclusiones y calcular la comparación equivalente (denominador de 365 días con vacíos, ND con media 0) frente a la no equivalente (razón 3,87) en `docs/evidence/008/equivalence.md`
- [x] T008 [US1] [A0] V4: contar con y sin sintéticos y reproducción y demostrar que las cifras reales no los incluyen; evidencia en `docs/evidence/008/exclusion.md`
- [x] T009 [US1] [A0] Capturar el panel con los filtros de cada conclusión en `docs/evidence/008/C1.png`, `C2.png`, `C3.png` (navegador real)
- [x] T010 [US1] [A0] Redactar el apartado «Análisis» en `docs/report.md` (cifras, filtros, periodo, unidad, sin valor, captura, consulta, instante, avisos; sin predicción ni riesgo)

**Checkpoint**: US1 verificable por sí sola.

---

## Phase 4: User Story 2 - Complejidad y rendimiento (Priority: P1)

**Goal**: tres operaciones medidas con tres tamaños y la API con 1.000.000 de filas.

**Independent Test**: V5–V7.

- [x] T011 [P] [US2] [A1] Crear `tests/benchmark/structure_benchmark.py`: búsqueda de versiones por id (lista secuencial, diccionario), integración geográfica (punto en polígono ingenuo frente a índice espacial), agregación por ventanas (bucle con diccionario frente a `GROUP BY` con `date_bin` sobre `bench`), con n = 10.000, 100.000 y 1.000.000, mediana de repeticiones tras calentamiento, pico con `tracemalloc`, salida JSON y Markdown, esquema `bench` eliminado al terminar aunque falle; sin tocar `core` ni `replay`
- [x] T012 [P] [US2] [A1] Crear `tests/benchmark/test_structure_benchmark.py` (pytest, comportamiento): con n pequeños la salida tiene las tres operaciones y variantes, resultados idénticos entre variantes y `bench` no existe después; no ejecutar `tests/db`
- [x] T013 [US2] [A0] Verificar lo entregado por A1, ejecutar `docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m tests.benchmark.structure_benchmark` y guardar salida en `docs/evidence/008/structure-benchmark.md` y `.json`
- [x] T014 [US2] [A1] Ampliar `tests/benchmark/api_latency.py` solo lo necesario para medir con 1.000.000 de filas sintéticas según la decisión de T003, sin repetir lo medido en la 006; añadir prueba en `tests/benchmark/test_api_latency_scale.py`. Si T003 concluyó que requiere cambio en `api/`, esta tarea se suspende y se documenta
- [x] T015 [US2] [A0] Ejecutar la medición de la API con 1.000.000 (o el máximo alcanzable, documentado), comprobar que `core` no cambió y que `bench` ya no existe (V7); evidencia en `docs/evidence/008/api-latency-1m.md`
- [x] T016 [US2] [A0] Redactar en `docs/report.md` el apartado «Complejidad y rendimiento»: coste medio y peor caso de las tres operaciones, tablas de medidas y de supuestos separadas, equipo y procedimiento, enlace a la medición de la 002 (`docs/evidence/002/index-benchmark.md`), razonamiento de 100 M como supuesto y enlace a «Razonamiento para 100 millones» ya existente (sin duplicarlo)

**Checkpoint**: US2 verificable sin US1.

---

## Phase 5: User Story 3 - Costes (Priority: P2)

**Goal**: informe de costes sin beneficios inventados.

**Independent Test**: V8.

- [x] T017 [US3] [A0] Medir tamaños reales (base, volúmenes de Kafka, bytes de una respuesta de la API y peticiones por día cada 60 s) y guardarlos en `docs/evidence/008/cost-measurements.md`
- [x] T018 [P] [US3] [A0] Consultar los límites actuales de Netlify y ngrok (plan gratuito) en su documentación oficial y anotar fecha, enlace y consecuencia de superarlos en `docs/evidence/008/free-tier-limits.md`
- [x] T019 [US3] [A2] Con T017 y T018 y los supuestos que fije la sesión principal (potencia, tarifa, horas, amortización), preparar la tabla de partidas «Medida/Supuesto» en `docs/evidence/008/cost-table.md`; no inventar importes
- [x] T020 [US3] [A0] Revisar `docs/evaluacion-financiera.md` frente al principio IX: retirar o justificar cada flujo, ROI «no estimado» salvo beneficio medible definido por la persona autora; reescribir el fichero
- [x] T021 [US3] [A0] Redactar en `docs/report.md` el apartado «Costes» (partidas, cuotas gratuitas, escalado y mejoras, ROI)

**Checkpoint**: US3 verificable.

---

## Phase 6: User Story 4 - Trazabilidad y cierre (Priority: P2)

**Goal**: matrices, coherencia e higiene.

**Independent Test**: V9–V12.

- [x] T022 [US4] [A0] Construir la matriz de las 11 pruebas de §11 (spec, evidencia, estado, hueco) en `docs/evidence/008/matrix-11.md`; ninguna superada sin evidencia
- [x] T023 [P] [US4] [A2] Preparar las tablas de entregables de §12 y criterios de §13 contra ficheros y secciones de `docs/report.md` en `docs/evidence/008/matrix-12-13.md`, a partir de T002
- [x] T024 [US4] [A0] Verificar T023 y volcar las tres matrices en `docs/report.md` (apartado «Trazabilidad»)
- [x] T025 [US4] [A0] Revisar `docs/report.md`: índice, enlaces (todos resuelven) y cifras repetidas coherentes; corregir y registrar en `docs/evidence/008/report-coherence.md`
- [x] T026 [US4] [A0] Revisión de higiene con `git ls-files` (sin `node_modules`, `.env`, volúmenes, datos, copias `*.bak`/`*.orig`) y búsqueda de secretos sin imprimirlos; resultado en `docs/evidence/008/repository-hygiene.md`; no reescribir historia sin confirmación
- [x] T027 [US4] [A0] Redactar los huecos de la persona autora (Linux de las specs 002, 003, 005 y 006; panel desde otro dispositivo) con procedimiento y ruta de evidencia en `docs/evidence/008/user-gaps.md` y enlazarlos desde la matriz

---

## Phase 7: User Story 5 - Guion de apoyo (Priority: P3)

**Independent Test**: seguir el guion con el sistema levantado.

- [x] T028 [US5] [A2] Redactar `docs/guion-explicacion.md` con el flujo USGS → Kafka → consumidor → PostgreSQL → API → panel, decisiones y enlace a la evidencia de cada etapa, a partir de `docs/report.md` y `docs/evidence/`; sin redactar decisiones propias de la persona autora
- [x] T029 [US5] [A0] Revisar T028 y comprobar que cada enlace resuelve

---

## Phase 8: Polish y cierre

- [x] T030 [A0] `docs/evidence/008/README.md`: resumen V1–V12 con esperado/observado y estado
- [x] T031 [A0] Ejecutar una sola vez los tests nuevos y `tests/db` si se tocó algo de la base; guardar salida en `docs/evidence/008/tests.txt`
- [x] T032 [A0] Actualizar la memoria del proyecto (`MEMORY.md` y fichero de estado de la spec 008), revisar `git status`, y commit sin `git add -A`; sin push

---

## Dependencias

- Setup → Foundational → US1 y US2 (independientes entre sí) → US3 (usa medidas de US2) → US4 (usa todo) → US5 → Polish.
- T011 y T012 en paralelo (ficheros distintos); T013 espera a ambos. T014 no solapa con T011 (distinto fichero) pero espera a T003.
- T018 y T023 son paralelizables con otras tareas de su fase.

## Estrategia

MVP: Phase 1–3 (US1). Después US2, y el resto por prioridad. Una historia por sesión si se agota el contexto.

## Resumen

32 tareas: Setup 2, Foundational 2, US1 6, US2 6, US3 5, US4 6, US5 2, Polish 3.
