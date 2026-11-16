---

description: "Task list for feature 007: Angular dashboard conforming to the statement"
---

# Tasks: Panel Angular conforme al enunciado

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/ui-contract.md](contracts/ui-contract.md),
[quickstart.md](quickstart.md); contrato de datos `specs/006-query-api/contracts/api.md`

**Tests**: incluidas (principio IX, FR-038). Pruebas de comportamiento de la lógica pura en
`frontend/src/app/lib/*.test.ts` (Vitest): comprueban resultados de funciones, nunca la presencia de
texto en el código. Lo visual se comprueba en navegador real (quickstart V1–V15).

**Reglas**: código, nombres y comentarios en inglés; textos visibles y documentación en español.
LF. Nunca leer ni imprimir `.env`; no ejecutar `docker compose config`. Sin cambios en `api/`
(plan; solo con necesidad demostrada y documentada). Versiones de Angular, ngx-leaflet y Leaflet
fijadas; única dependencia nueva `vitest` (dev, versión exacta). Nada de datos ni secretos en Git.
`docker compose down -v` pide confirmación explícita. Texto de usuario siempre como texto, nunca
HTML.

**Agentes** (etiqueta `[A#]`, norma «Orquestación de agentes» de `CLAUDE.md`):

- `[A0]` sesión principal: servicio de datos, estado, configuración, `app.component.*`, todo lo que
  toca el sistema real (Docker, navegador), evidencias, memoria e integración.
- `[A1]` agente nuevo en segundo plano, **Sonnet**: lógica pura de `lib/` y componentes con sus pruebas.
- `[A2]` agente nuevo en segundo plano, **Haiku**: documentación (README, informe) a partir de la evidencia.

Cada agente recibe un prompt corto que apunta a este fichero y a los contratos (nunca `fork`), solo
toca los ficheros de su tarea y ejecuta solo sus pruebas (`npx vitest run <fichero>` en `frontend/`).
No hacen commit, no tocan `.env`, no ejecutan `down -v` e informan en menos de 200 palabras.
`[P]` = paralelizable con otras `[P]` de la misma fase porque sus ficheros no se solapan.
`app.component.*` y `observatory.service.ts` los edita solo `[A0]`.

## Format: `[ID] [P?] [Story] [Agente] Description`

---

## Phase 1: Setup

- [X] T001 [A0] Vitest 3.2.7 (la 5.x no es compatible con el peer de `@angular/build` 20.3.0); añadida como dependencia de desarrollo con versión exacta en `frontend/package.json` y `frontend/package-lock.json`; script `"test": "vitest run"`; `frontend/vitest.config.ts` (entorno `node`, `include: src/app/lib/**/*.test.ts`)
- [X] T002 [A0] Nueva forma de `frontend/public/config.json`: `mode` (`live`|`replay`), `apiUrl`, `refreshMs` 60000, `requestTimeoutMs` 15000, `staleAfterMs` 900000, `skipNgrokWarning` true; retirar `frontend/public/datos/terremotos-demo.geojson`; `<html lang="es">` en `frontend/src/index.html`
- [X] T003 [P] [A1] Tipos del contrato de la 006 y de las respuestas adaptadas (`EventsPage`, `MapEvent`, `Statistics`, `Health`, `ApiFailure`, `QueryFilters`, `Reading`, `PanelStatus`) en `frontend/src/app/lib/api-types.ts`, según [data-model.md](data-model.md)

---

## Phase 2: Foundational (bloquea todas las historias)

- [X] T004 [P] [A1] Formato en `frontend/src/app/lib/format.ts` y pruebas en `format.test.ts`: `null`, `undefined`, `NaN` e infinitos → «ND» para magnitud y profundidad con el mismo criterio (el 0 es un valor válido y se muestra como 0); instantes ms → ISO UTC con «UTC»; país nulo → «Sin país asignado»; continente y subregión nulos → texto de ausencia
- [X] T005 [P] [A1] Adaptadores en `frontend/src/app/lib/adapt.ts` y `adapt.test.ts`: `adaptEvents`, `adaptStatistics`, `adaptHealth` según el contrato de la 006; forma inesperada → `ApiFailure` `invalid_response` sin lanzar al componente; exige `metadata.mode` igual al pedido y, en `replay`, `metadata.label` no vacía; conserva `null` sin convertir; usa `country_id`/`country_name`; descarta con motivo las features sin geometría
- [X] T006 [P] [A1] Filtros en `frontend/src/app/lib/filters.ts` y `filters.test.ts`: `eventParams(filters, limit, offset)` y `statsParams(filters)` desde un único `QueryFilters`; fechas con `Z` explícito (nunca la zona del navegador); `exclude_synthetic` solo en `replay`; sin `format`, `limit` ni `offset` en estadísticas; validación `start < end` y `min_mag` finito (devuelve errores por campo)
- [X] T007 [P] [A0] Estado en `frontend/src/app/lib/status.ts` y `status.test.ts`: `derivePanelStatus(reading, failure, health, now, staleAfterMs)` con la prioridad de [ui-contract.md](contracts/ui-contract.md): inaccesible > 503 > 422 > degradado > desactualizado > sin eventos > ok, avisos compatibles acumulados; antigüedad frente a `generated` de la lectura, con el reloj local solo como alternativa; cero eventos válidos no es error
- [X] T008 [P] [A0] Configuración en `frontend/src/app/lib/config.ts` y `config.test.ts`: validar `config.json` (`mode` ∈ {live, replay}, `apiUrl` sin barra final ni `/api`, `refreshMs` con suelo de 5000, valores por defecto); `demo` es inválido
- [X] T009 [A0] Servicio de lectura `frontend/src/app/data/observatory.service.ts`: `fetch` con `AbortSignal.timeout(requestTimeoutMs)`, cabecera `ngrok-skip-browser-warning` si procede, ciclo con `setTimeout` rearmado al terminar (nunca dos peticiones a la vez), número de secuencia que descarta respuestas anteriores, aborto al cambiar filtros o modo, lectura conservada tras un fallo, no-JSON → `unreachable`; expone señales de lectura, fallo y estado derivado
- [X] T010 [A0] Reducir `frontend/src/app/app.component.ts|html|css` a la composición (estado, filtros, mapa, tabla, análisis) y eliminar el formato antiguo (`countries`, `timeline`, `bucket`, `daily_average_2025`, `format`, `country`)

**Checkpoint**: `npm test` verde y `npm run build` sin errores; el panel compila contra los tipos nuevos.

---

## Phase 3: User Story 1 - Mapa y tabla con la API real (P1) 🎯 MVP

**Objetivo**: mapa y tabla con los eventos de 24 h, nulos como ND, marítimo sin país, ficha como texto.

**Prueba independiente**: con el stack levantado, mapa y tabla muestran los mismos eventos que la API (V1–V5).

- [X] T011 [P] [US1] [A1] Lógica del mapa en `frontend/src/app/lib/geo.ts` y `geo.test.ts`: validación de coordenadas (finitas, lon ∈ [-180,180], lat ∈ [-90,90]) con recuento de omitidos; radio por magnitud (mínimo y borde discontinuo con ND); categoría y color por profundidad (< 70, 70–299,99, ≥ 300 km, ND); texto de la ficha (id, magnitud, profundidad, hora UTC, país, continente, subregión; en replay `replayed_at` y sintético) como cadenas, sin HTML
- [X] T012 [US1] [A1] Componente `frontend/src/app/map/map.component.ts|html|css`: mapa Leaflet con fondo, fronteras (`paises.geojson`), una sola capa «Terremotos» que se sustituye completa en cada lectura correcta y no se toca en un fallo, ficha con `textContent`, leyenda (profundidad, tamaño, ND), contador de dibujados y omitidos; usa `geo.ts`
- [X] T013 [P] [US1] [A1] Componente `frontend/src/app/table/table.component.ts|html|css`: tabla con `<caption>`, `th scope="col"`, todos los campos (id, hora UTC, magnitud, tipo, profundidad, lugar, país, continente, subregión y, en replay, `replayed_at` y sintético), magnitud y profundidad en texto con ND; solo la página recibida por ahora
- [X] T014 [US1] [A0] Integrar mapa y tabla en `app.component.html` alimentados por la lectura del servicio; comprobar con `npm run build`
- [X] T015 [US1] [A0] Verificar V1–V5 con el stack levantado (skill `verify-stack`) y navegador; evidencia en `docs/evidence/007/V1-V5-*.md` y capturas

**Checkpoint**: MVP — el panel carga con la API de la 006 y muestra eventos reales.

---

## Phase 4: User Story 2 - Frescura de los datos y estado del backend (P1)

**Objetivo**: tres instantes rotulados, avisos, última lectura conservada y recuperación automática.

**Prueba independiente**: parar y reabrir la API con el panel abierto (V11–V13).

- [X] T016 [P] [US2] [A1] Componente `frontend/src/app/status/status.component.ts|html|css`: tres instantes rotulados (última lectura del panel, generación de la respuesta, última ingesta), periodo consultado, modo, mensajes distintos para cada estado de [ui-contract.md](contracts/ui-contract.md), última lectura rotulada con su hora, `aria-live="polite"` y `assertive` solo para inaccesible
- [X] T017 [US2] [A0] Integrar el estado en `app.component.html` y la petición de `/api/salud` en el ciclo del servicio; aviso de truncado visible del mapa y la tabla («Se muestran N de TOTAL…»)
- [X] T018 [US2] [A0] Verificar V11 (cerrar y reabrir), V12 (503, `degraded`, 422, desactualizado) y V13 (sin solapes, 15 s); evidencia en `docs/evidence/007/V11-V13-*.md` con la hora de cada transición

---

## Phase 5: User Story 3 - Filtros coherentes entre vistas (P1)

**Objetivo**: fecha UTC, magnitud mínima y país por identificador; mismos totales en mapa, tabla y gráficos.

**Prueba independiente**: batería de filtros con totales idénticos (V7–V8).

- [X] T019 [P] [US3] [A1] Catálogo de países en `frontend/src/app/lib/countries.ts` y `countries.test.ts`: de `paises.geojson` extraer `ADM0_A3` (identificador) y `NAME_ES` con alternativa `ADMIN`, ordenados por nombre sin duplicados; el «Sin país asignado» no forma parte del catálogo
- [X] T020 [US3] [A1] Componente `frontend/src/app/filters/filters.component.ts|html|css`: desde/hasta con etiqueta «(UTC)», magnitud mínima, selector de país con texto que explica por qué «Sin país asignado» no es filtrable, aplicar y restablecer, errores junto al campo (de `filters.ts`); emite un único `QueryFilters`
- [X] T021 [US3] [A0] Conectar el `QueryFilters` único con el servicio: la misma petición de filtros alimenta mapa, tabla y estadísticas; conservar la última vista válida ante un 422; descartar respuestas de filtros anteriores
- [X] T022 [US3] [A0] Verificar V7 (batería: solo fecha, `min_mag`, país, combinados, con totales de mapa = tabla = `total` de estadísticas) y V8 (inicio ≥ fin, > 10.000 h); capturas de los filtros usados en `docs/evidence/007/V7-V8-*.md`

---

## Phase 6: User Story 5 - Reproducción aislada y etiquetada (P1)

**Objetivo**: selector de modo, «REPRODUCCIÓN» desde `metadata.label`, limpieza al cambiar.

**Prueba independiente**: totales reales → reproducción → volver; idénticos (V9–V10).

- [X] T023 [US5] [A1] Selector de modo (Real | Reproducción) y conmutador «Excluir sintéticos» (solo replay) en `frontend/src/app/filters/filters.component.*`; muestra `last_replayed_at` en el estado (`status.component.*`) y la etiqueta de `metadata.label` en mapa, tabla y análisis (rótulo recibido como entrada de cada componente)
- [X] T024 [US5] [A0] Cambio de modo en el servicio: abortar, secuencia+1, vaciar lectura, mapa, tabla y gráficos antes de pedir en el nuevo modo; rechazar respuesta de modo distinto o sin etiqueta (ya validado en `adapt.ts`) y avisar; en replay no aplicar ventana de 24 h
- [X] T025 [US5] [A0] Verificar V9 y V10 con una reproducción real de la spec 005 y sintéticos; evidencia en `docs/evidence/007/V9-V10-*.md` con los totales reales antes y después

---

## Phase 7: User Story 4 - Análisis: horas, países, distribuciones y comparación (P2)

**Objetivo**: gráficos con tabla equivalente, cada resultado con periodo, filtros, unidad y sin valor.

**Prueba independiente**: cifras del panel = `/api/estadisticas` con los mismos filtros.

- [X] T026 [P] [US4] [A1] Preparación de datos de gráfico en `frontend/src/app/lib/chart-data.ts` y `chart-data.test.ts`: barras por hora UTC (ceros incluidos; más de 168 ventanas: dibujar las últimas 168 y señalarlo, sin recalcular cifras), por país (las 15 mayores, «Sin país asignado» siempre visible, resto sumando solo filas ya entregadas), tramos de magnitud y profundidad con «ND» aparte; comparación con «ND» si `ratio` es `"ND"`; no recalcula totales ni estadísticas
- [X] T027 [US4] [A1] Componente `frontend/src/app/charts/charts.component.ts|html|css`: gráficos de barras HTML/SVG sin biblioteca, `role="img"` con descripción, tabla de valores equivalente por gráfico (`<details>`), cada resultado con periodo, filtros aplicados, unidad y registros sin valor, aviso de periodo incompleto (`warning` de la API), comparación recientes frente a media diaria de 2025, aviso de `map_truncated`, explicación del 422 de más de 10.000 horas; texto o etiqueta además de color
- [X] T028 [US4] [A0] Integrar los gráficos en `app.component.html` con la `Statistics` de la lectura; verificar que el total mostrado coincide con `metadata.total` de eventos para cada filtro de la batería; evidencia en `docs/evidence/007/V4-V7-charts.md` (incluye evento marítimo bajo «Sin país asignado» en el gráfico por país)

---

## Phase 8: User Story 6 - Tabla recorrible y accesible (P2)

**Objetivo**: recorrer todo el conjunto con `next_offset`, teclado y `aria-live`.

**Prueba independiente**: periodo con más de 1000 eventos, «Cargar más» hasta agotar; uso solo con teclado (V6, V14).

- [X] T029 [US6] [A1] Paginación en `frontend/src/app/table/table.component.*`: «Mostrando N de TOTAL» con `count` acumulado y `total`, botón «Cargar más» (operable con teclado, deshabilitado sin `next_offset`), sin repetidos, `aria-live` al cargar
- [X] T030 [US6] [A0] Servicio: petición de página siguiente con `offset = next_offset`, mismos filtros, misma secuencia; un refresco reinicia en la primera página e informa en la región de estado; límite de carga y fallo conservan lo ya cargado
- [X] T031 [US6] [A0] Revisión de accesibilidad: foco visible, etiquetas asociadas, contraste ≥ 4,5:1 (comprobado), información no solo por color, orden de tabulación; verificar V6 (truncado y paginación con más de 1000 eventos, usando el conjunto sintético de la spec 002 si hace falta) y V14; evidencia en `docs/evidence/007/V6-V14-*.md`

---

## Phase 9: User Story 7 - Despliegue en Netlify tras el túnel (P2)

**Objetivo**: configuración y procedimiento; la publicación real la hace la usuaria.

**Prueba independiente**: seguir el README hasta tener el panel funcionando en local con la API; build limpio (V15).

- [X] T032 [US7] [A0] Revisar `netlify.toml` (base `frontend`, publicación `dist/observatorio/browser`), `frontend/public/_redirects`, `.env.example` (`CORS_ORIGINS` con el origen de Netlify y `http://localhost:4200`) y que `config.json` y el repositorio no contengan authtoken ni secretos (`git grep -i authtoken`); sin cambios en `api/`
- [X] T033 [P] [US7] [A2] Procedimiento de la defensa en `README.md`: levantar el túnel, fijar la URL HTTPS en `frontend/public/config.json` antes de compilar, `npm ci` y `npm start`, publicar en Netlify, autorizar el origen exacto en CORS, comprobar desde otro dispositivo y qué hacer si cambia la URL del túnel
- [X] T034 [US7] [A0] Verificar V15: `npm run build` y servir `dist/observatorio/browser` con la configuración; comprobar que el paquete no contiene secretos; evidencia en `docs/evidence/007/V15-*.md`

---

## Phase 10: User Story 8 - Evidencia y cierre (P3)

- [X] T035 [US8] [A0] Completar `docs/evidence/007/` (índice con esperado/observado y capturas con los filtros usados de V1–V15); la comprobación con Netlify y ngrok reales se deja como pendiente de la usuaria, indicada como tal
- [X] T036 [US8] [A2] Apartado de la spec 007 en `docs/report.md` a partir de la evidencia: qué muestra el panel, decisiones, divergencias resueltas del panel entregado y estado de cada prueba (superada solo con evidencia)

---

## Phase 11: Polish & cross-cutting

- [X] T037 [A0] Ejecutar la suite completa (`npm test`, `npm run build`) una vez y repasar `git status` y `git diff --stat`: sin `.env`, datos ni copias; LF; sin símbolos de enlaces tocados
- [X] T038 [A0] Actualizar la memoria (`MEMORY.md` y un fichero de estado de la 007) con el estado, lo pendiente (Netlify y ngrok reales, prueba en Linux) y el traspaso a la 008; commit tras revisar lo entregado

---

## Dependencies & Execution Order

- Fase 1 → Fase 2 (T004–T008 en paralelo tras T003; T009 tras T005–T008; T010 tras T009).
- Fases 3, 4, 5 y 6 dependen de la 2. **US1 (fase 3) es el MVP** y las demás se apoyan en su mapa y tabla;
  orden recomendado: 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11.
- US3 (filtros) y US5 (modo) comparten `filters.component.*`: T023 va después de T020.
- US4 (gráficos) necesita la lectura con estadísticas del servicio (T009) y los filtros (T021).
- US6 amplía `table.component.*` (T013 antes de T029).

## Parallel Opportunities

- T004, T005, T006 (`A1`) y T007, T008 (`A0`) tocan ficheros distintos: se lanzan a la vez.
- T011 y T013 (A1) en paralelo; T012 tras T011.
- T016 (A1) mientras A0 integra T014.
- T019 y T026 (A1) en paralelo con trabajo de A0 en el servicio.
- T033 (A2) en paralelo con T032/T034.

## Implementation Strategy

1. **MVP**: Fases 1 a 3: el panel carga sin NG0900 y pinta mapa y tabla con la API de la 006.
2. **Incremento P1**: estado y túnel (4), filtros (5) y reproducción (6) — en este orden, cada uno verificado antes de pasar al siguiente.
3. **P2**: análisis (7), tabla recorrible y accesibilidad (8), despliegue (9).
4. **Cierre**: evidencia, informe, memoria y commit (10–11). Ninguna prueba se da por superada sin evidencia en `docs/evidence/007/`.
