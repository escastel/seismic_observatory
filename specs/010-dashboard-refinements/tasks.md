---

description: "Task list for feature 010: dashboard layout, alerts, no-events handling and map refinements"
---

# Tasks: Ajustes de diseño, distribución y filtrado del panel

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/ui-contract.md](contracts/ui-contract.md), [quickstart.md](quickstart.md); mockup aprobado en `references/mockup/`

**Tests**: incluidas (principio IX, FR-029). Vitest para la lógica pura nueva en `frontend/src/app/lib/*.test.ts` (resultados de funciones, nunca la presencia de texto en el código) y pytest para la
corrección de la API en `tests/query_api/test_statistics.py`. Lo visual se comprueba en navegador real (quickstart X1 a X16).

**Reglas**: código, nombres y comentarios en inglés; textos visibles y documentación en español. LF. Nunca leer ni imprimir `.env`; no ejecutar `docker compose config`. Sin dependencias nuevas.
**No se tocan** `adapt.ts`, `api-types.ts`, `filters.ts`, `status.ts` ni `config.ts`; el único cambio de la lógica de datos de la 007 es `observatory.service.ts` (tolerancia, R7), documentado (FR-028). La API solo cambia
`api/app/stats.py` (corrección que hace cumplir el contrato). Sin claves ni credenciales. Texto de usuario siempre como texto. Ninguna petición de teselas ni de placas por el túnel. `docker compose down -v` pide
confirmación explícita. Nunca dos ejecuciones de `tests/db` a la vez (no se tocan). **Desplegar a Netlify (publica el panel) ocurre al integrar en `main` y pide confirmación explícita.**

**Agentes** (etiqueta `[A#]`, norma «Orquestación de agentes» de `CLAUDE.md`):

- `[A0]` sesión principal: API, `observatory.service.ts`, mapa, integración en `app.component.*`, `styles.css`, todo lo que toca el sistema real (Docker, navegador, ngrok), evidencias, memoria y commit.
- `[A1]` agente nuevo en segundo plano, **Sonnet**: lógica pura de `lib/` con sus pruebas y componentes autocontenidos.
- `[A2]` agente nuevo en segundo plano, **Haiku**: documentación a partir de la evidencia ya guardada (nunca inventa cifras).

Cada agente recibe un prompt corto que apunta a este fichero y a los contratos (nunca `fork`), solo toca los ficheros listados en su tarea y no hace commit. Dos agentes a la vez solo si sus ficheros no se solapan.
Los agentes ejecutan solo `npx vitest run <fichero>`; la sesión principal ejecuta la suite completa y la compilación una vez.

## Format: `[ID] [P?] [Story] [A#] Descripción con ficheros`

---

## Phase 1: Setup

- [X] T001 [A0] Comprobar la rama `010-dashboard-refinements` y `.specify/feature.json`; `npm ci` y `npm test` en `frontend/` y guardar el estado base (pruebas y ficheros, versiones, equipo) en `docs/evidence/010/00-environment.md`; comprobar que la API local responde y anotar el recuento de `GET /api/eventos?country_id=ALB` (0)

---

## Phase 2: Foundational (bloquea las historias)

- [X] T002 [A0] Actualizar `frontend/src/styles.css`: tokens de colores de avisos (`--alert-error`, `--alert-warning`, `--alert-info`, `--alert-success` con los tonos de `research.md` R2 en oscuro y claro), estructura de tema con **oscuro como base**, claro bajo `@media (prefers-color-scheme: light) { :root:not([data-theme="dark"]) { … } }` y bajo `:root[data-theme="light"]`, color de acento de «Seismic», y reglas globales de `prefers-reduced-motion` (research R6)
- [X] T003 [P] [A1] Ampliar `frontend/src/app/lib/theme.ts` con `type ThemePreference = 'auto' | 'dark' | 'light'`, `resolvePreference(stored: string | null, deviceLight: boolean | null): ThemePreference` (valor guardado no válido o `null` → `'auto'`) y `effectiveTheme(preference, deviceLight): Theme` (manual manda; en `auto`, oscuro si el dispositivo no expresa preferencia); pruebas en `lib/theme.test.ts` (data-model: ThemePreference)
- [X] T004 [P] [A1] Crear `frontend/src/app/lib/alerts.ts` y `lib/alerts.test.ts`: `Alert { id; kind: 'error' | 'warning' | 'info' | 'success'; text; role: 'alert' | 'status'; autoDismissMs: number | null }`; `buildAlerts(input)` desde `PanelStatus` (claves y mensajes de `status.ts`), `statsFailure`, truncado (`events.length < total`), modo reproducción, `configError`, aviso de países no disponibles y avisos de capa; `role: 'alert'` solo para `error`; `autoDismissMs: 8000` solo para `success`; orden error, warning, info, success; sin duplicados por `id`; y `noEventsText(filters, countryName)` que devuelve `{ title: 'No hay eventos registrados con las condiciones del filtro', conditions: string[], suggestion: string }` (país, periodo UTC, magnitud mínima y modo; con un solo país y el periodo por defecto, título «No hay eventos sísmicos ahora mismo en <país>») (data-model: Alert; spec FR-022)
- [X] T005 [P] [A1] Crear `frontend/src/app/lib/status-bar.ts` y `lib/status-bar.test.ts`: `buildStatusBar(statistics, status, reading)` reutilizando `lib/summary.ts` sin modificarlo; devuelve `metrics` (5, con `visibleOnNarrow` en `total`, `lastIngestion` y `status`) y `details` (última lectura correcta del panel, generación de la respuesta, última ingesta, última reproducción solo en reproducción, cuarentena con geometría no válida, eventos sin magnitud incluidos o excluidos); `ND` sin dato; etiqueta «REPRODUCCIÓN» en reproducción; ninguna cifra sale de eventos del mapa (data-model: StatusBar)
- [X] T006 [P] [A1] Crear `frontend/src/app/lib/filter-chips.ts` y `lib/filter-chips.test.ts`: `filterChips(filters, countryName)` → `{ id; label }[]` para modo, periodo, magnitud mínima y país de los filtros **aplicados**; «Todos los países» y «Sin mínimo de magnitud» cuando no hay filtro; texto sin HTML (data-model: FilterChip)
- [X] T007 [P] [A1] Crear `frontend/src/app/lib/stats-tolerance.ts` y `lib/stats-tolerance.test.ts`: `statsFailureKeepsEvents(failure: ApiFailure): boolean` con `true` para `invalid_parameters` y `invalid_response` y `false` para `unreachable` y el resto (research R7)
- [X] T008 [P] [A1] Crear `frontend/src/app/lib/cluster-style.ts` y `lib/cluster-style.test.ts`: `clusterStyle(count): { size: number; level: 1 | 2 | 3 | 4 }` con `< 10` → 34 px y nivel 1, `< 50` → 44 px y nivel 2, `< 200` → 54 px y nivel 3, `≥ 200` → 64 px y nivel 4, y `HEAT_GRADIENT` con `{0.2:'#ffe066', 0.4:'#ffb347', 0.6:'#ff7a3d', 0.8:'#e03b2e', 1.0:'#8b0f1c'}`, `HEAT_OPTIONS` (`radius: 30`, `blur: 20`, `minOpacity: 0.45`, `maxZoom: 6`) y `haloRadius(radius)` (data-model: ClusterStyle)
- [X] T009 [P] [A1] Actualizar `frontend/src/app/lib/map-layers.ts` y `lib/map-layers.test.ts`: quitar el fondo `relief` y su URL, su filtro y la atribución de Esri; `BaseLayerId = 'simple' | 'satellite'`; `platesDefault` devuelve `true` para ambos fondos y `OVERLAY_LAYERS` marca `plates` con `defaultEnabled: true`; el resto sin cambios (research R5)

**Checkpoint**: tokens y lógica pura verificadas con Vitest; la API y el panel aún no cambian.

---

## Phase 3: User Story 3 - Filtrar sin eventos (Priority: P1) 🎯 MVP (corrige el fallo real)

**Goal**: ningún filtro sin resultados deja datos de otro filtro; aviso emergente claro.

**Independent Test**: X1, X2 y X3.

- [X] T010 [US3] [A0] **Prueba primero**: añadir a `tests/query_api/test_statistics.py` pruebas de comportamiento: con el periodo por defecto en vivo y un filtro que no coincide con ningún evento, `GET /api/estadisticas` devuelve `period.start` y `period.end` numéricos, `total` 0, `hourly.items` con 24 ventanas a cero; con un periodo dado sin eventos, los valores dados; en modo reproducción sin eventos ni inicio, `period.start == period.end` y `hourly.items` vacío; y que con eventos nada cambia; ejecutarlas y comprobar que **fallan** antes del arreglo (`docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m pytest tests/query_api/test_statistics.py -q`)
- [X] T011 [US3] [A0] Corregir `api/app/stats.py::hourly_counts` (research R1): si `end` es `None` y no hay eventos, `end = now`; si `start` es `None`, `start = end`; sin tocar ningún otro campo ni el contrato; reconstruir con `docker compose up --build -d api`, repetir T010 hasta que pasen y guardar la salida en `docs/evidence/010/x1-api-fix.md` (contrato de la 006 intacto; cambio justificado)
- [X] T012 [US3] [A0] En `frontend/src/app/data/observatory.service.ts` sustituir la condición `adaptedStats.failure.kind === 'invalid_parameters'` por `statsFailureKeepsEvents(adaptedStats.failure)` (T007): con eventos válidos y estadísticas no válidas la lectura nueva lleva `statistics = null` y `statsFailure`; documentar el cambio en el encabezado del fichero y en `docs/evidence/010/x1-api-fix.md`
- [X] T013 [P] [US3] [A1] Crear `frontend/src/app/map/no-events-popup.component.ts|html|css` (componente standalone, OnPush): tarjeta flotante no modal con título, lista de condiciones, sugerencia y botón de cierre accesible; `input()` con el resultado de `noEventsText` y `output()` de cierre; `role="status"` con `aria-hidden="true"` mientras la zona de avisos anuncia lo mismo; sin robar el foco; tokens de `styles.css`; transición solo con movimiento permitido
- [X] T014 [US3] [A0] Cablear el aviso: `map/map.component.html|ts` muestra `<app-no-events-popup>` cuando la lectura es correcta con `total = 0` (cualquier filtro, periodo o modo), se vuelve a mostrar tras cada nuevo filtro sin eventos y desaparece al llegar eventos; el texto sale de `noEventsText` (T004) con el nombre del país del catálogo
- [X] T015 [US3] [A0] Verificar X1 a X3 en navegador real: Albania con el sistema real (periodo por defecto y con 2025 completo), un país con eventos, mínimo de magnitud muy alto, reproducción sin eventos y el simulador de contrato con estadísticas sin `period.end`; capturas y JSON en `docs/evidence/010/x2-x3-no-events.md`

**Checkpoint**: US3 verificable por sí sola.

---

## Phase 4: User Story 1 - El mapa primero y página compacta (Priority: P1)

**Goal**: cabecera, barra de estado, filtros y mapa en el orden y con el diseño del mockup.

**Independent Test**: X4, X5, X7 y X8.

- [X] T016 [P] [US1] [A1] Crear `frontend/src/app/status-bar/status-bar.component.ts|html|css`: barra con cinco métricas y botón «Detalles» (`aria-expanded`, `<details>` o equivalente accesible) que despliega los `details` de `lib/status-bar.ts`; ≤ 760 px solo `visibleOnNarrow`; `ND`; sin título «Estado del panel»; estilos del mockup en ambos temas; `input()` de `statistics`, `status`, `reading` y `label`
- [X] T017 [P] [US1] [A1] Reestructurar `frontend/src/app/filters/filters.component.html|css` (y `.ts` solo lo imprescindible, sin tocar `lib/filters.ts`): bloque con título «Filtros», controles en una sola fila con `flex-wrap`, chips de los filtros aplicados (`input()` con `filterChips` de T006), y en ≤ 760 px botón «Filtros» (`aria-expanded`) que despliega el formulario con los chips visibles; mismos mensajes de validación junto al campo que en la 007
- [X] T018 [US1] [A0] Reescribir la cabecera y el orden en `frontend/src/app/app.component.ts|html|css` y `frontend/src/index.html`: quitar `eyebrow` y `tagline`, `<h1><span class="brand-s">Seismic</span> Observatory</h1>` (en claro, texto oscuro y acento con contraste), `<title>Seismic Observatory</title>`, orden cabecera, avisos (hueco para la historia 2), barra de estado, filtros, mapa, gráficos, tabla; sustituir `app-summary` y `app-status` por `app-status-bar`; eliminar los directorios `frontend/src/app/status/` y `frontend/src/app/summary/` (la lógica de `lib/status.ts` y `lib/summary.ts` se conserva y se reutiliza) (research R3, R8)
- [X] T019 [US1] [A0] Maquetar los controles dentro del mapa en `map/map.component.html|css` como el mockup: selector de fondo y capas arriba a la derecha, leyenda abajo a la izquierda (plegable en móvil), chip de muestra arriba a la izquierda, alto `clamp(420px, 62vh, 760px)` y en móvil `56vh` con mínimo 340 px
- [X] T020 [US1] [A0] Verificar X4, X5, X7 y X8: cabecera en ambos temas, primera pantalla en 1440×900 y 390×844 (mapa a la vista), barra frente a `/api/estadisticas` en tres juegos de filtros, «Detalles», filtros en una línea y en móvil; capturas en `docs/evidence/010/x4-x8-layout.md`

---

## Phase 5: User Story 2 - Avisos independientes (Priority: P1)

**Independent Test**: X6.

- [X] T021 [P] [US2] [A1] Crear `frontend/src/app/alerts/alerts.component.ts|html|css`: lista de bloques independientes de `Alert[]` (T004) con borde, icono SVG y texto por tipo (✕ error, ▲ aviso, ⓘ información, ✓ éxito), `role` según el aviso, el de éxito se cierra solo a los 8 s, apilado por gravedad, sin ocupar espacio si no hay avisos, botón de cierre en los no críticos; colores de los tokens de T002 (contrato §3)
- [X] T022 [US2] [A0] Cablear los avisos en `app.component.ts|html`: calcular `buildAlerts` con el estado del servicio, el truncado, el modo, `configError`, el aviso de países y los avisos de capas que emite el mapa (`output()` `notice` de `map.component.ts`, que sustituye a su aviso interno); mostrar `app-alerts` entre la cabecera y la barra de estado; retirar los avisos antiguos dispersos del HTML
- [X] T023 [US2] [A0] Verificar X6 provocando cada situación (backend inaccesible con el túnel o la red bloqueada, datos desactualizados, 503 y respuesta no válida con el simulador, truncado, periodo > 10.000 h, fallo de fondo bloqueando el dominio, reproducción, sin eventos, recuperación): tipo, color, icono, texto y rol; capturas en `docs/evidence/010/x6-alerts.md`

---

## Phase 6: User Story 4 - Mapa más visual (Priority: P2)

**Independent Test**: X9, X10 y X11.

- [X] T024 [US4] [A0] En `map/map.component.ts` (y `.css`): selector solo con Simple y Satélite (catálogo de T009), placas activadas por defecto sobre ambos fondos y opcionales, retirar el fondo Relieve y su rama de código, **calor** con `HEAT_GRADIENT` y `HEAT_OPTIONS` (T008) y peso por magnitud (mínimo sin magnitud, nunca cero), leyenda de colores («Menos eventos → Más») y rótulo «densidad de eventos de la muestra · N de TOTAL»
- [X] T025 [US4] [A0] En `map/map.component.ts` y `frontend/src/styles.css`: **agrupación** con `iconCreateFunction` propio (`L.divIcon`) usando `clusterStyle` (tamaño y nivel por recuento, anillo y cifra), clases globales `so-cluster` y `so-cluster--1..4` en `styles.css` (Leaflet crea los iconos fuera del componente; en esa falta de estilos estaba la causa del «solo números»), y halo (`haloRadius`) detrás de los eventos sueltos con el mismo brillo; el rótulo «N de TOTAL» sigue visible
- [X] T026 [US4] [A0] Quitar los restos de Relieve y Esri: pie de página de `app.component.html`, atribuciones, `docs/` que lo citen como fondo disponible y `grep` del paquete compilado; comprobar que no queda ninguna referencia en `frontend/src` ni en `frontend/dist`
- [X] T027 [US4] [A0] Verificar X9 a X11 en ambos temas y fondos con un periodo largo (2025) y uno corto; capturas del calor y la agrupación (antes y después) en `docs/evidence/010/x9-x11-map.md`

---

## Phase 7: User Story 5 - Interruptor de tema (Priority: P2)

**Independent Test**: X12.

- [X] T028 [US5] [A0] Ampliar `frontend/src/app/theme/theme.service.ts`: señal `preference` (`'auto' | 'dark' | 'light'`), clave `seismic-theme` en `localStorage` con `try/catch` en lectura y escritura (el tema cambia aunque falle), `theme` calculado con `effectiveTheme` (T003), `toggle()` que alterna entre `dark` y `light` y guarda, y `data-theme` en `document.documentElement` solo con preferencia manual; `meta theme-color` por tema; los cambios del dispositivo solo cuentan en `auto`
- [X] T029 [P] [US5] [A1] Crear `frontend/src/app/theme-toggle/theme-toggle.component.ts|html|css`: botón flotante fijo abajo a la derecha con icono de sol u luna (SVG), `aria-label` «Cambiar a tema claro» o «Cambiar a tema oscuro» según el tema actual (lee `ThemeService.theme()` y llama a `ThemeService.toggle()` tal como los define T028), foco visible, tamaño táctil ≥ 44 px, transición solo con movimiento permitido (`ThemeService.reducedMotion()`)
- [X] T030 [US5] [A0] Integrar `app-theme-toggle` en `app.component.html` y verificar X12: alterna sin recargar y conserva la lectura, persiste tras recargar, funciona con `localStorage` bloqueado, teclado y lector de pantalla, sin animación con «reducir movimiento», y el mapa y los gráficos cambian con el tema; capturas en `docs/evidence/010/x12-theme-toggle.md`

---

## Phase 8: User Story 6 - Nada de lo verificado se pierde (Priority: P1)

**Independent Test**: X13 a X16.

- [X] T031 [US6] [A0] Accesibilidad (X13): axe-core (WCAG A y AA) en claro y oscuro con avisos visibles, «Detalles» abierto, el aviso emergente y las burbujas; recorrido con teclado y contraste de avisos, burbujas y el botón de tema; corregir lo que salga y guardar `docs/evidence/010/x13-a11y.json`
- [X] T032 [US6] [A0] No regresión (X14): `npm test` completo (las pruebas anteriores más las nuevas), `docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m pytest tests/query_api -q` una sola vez, V1 a V15 de la 007 y los escenarios W de la 009 con el panel nuevo, cierre y reapertura del túnel con el simulador; `git diff origin/main` vacío en `adapt.ts`, `api-types.ts`, `filters.ts`, `status.ts` y `config.ts`; evidencia en `docs/evidence/010/x14-regression.md`
- [X] T033 [US6] [A0] Peso y red (X15): `npm run build`, comparar el peso inicial con la 009 (`docs/evidence/009/w14-weight.json`) y, con el panel abierto y el túnel levantado, comprobar con el inspector de tráfico de ngrok que solo hay peticiones `/api/*` y ninguna de teselas ni de placas; evidencia en `docs/evidence/010/x15-weight-network.md`

---

## Phase 9: Polish y cierre

- [X] T034 [P] [A2] Con la evidencia de `docs/evidence/010/`, redactar `docs/evidence/010/README.md` (resumen de X1 a X16 con esperado/observado, estado y capturas enlazadas) sin inventar cifras
- [X] T035 [A0] Actualizar `docs/report.md` (apartado del panel: nueva distribución, avisos, barra de estado, mapa y botón de tema; el cambio justificado de `api/app/stats.py` y el de `observatory.service.ts`), `README.md` si cita el panel o el fondo Relieve, y revisar enlaces
- [ ] T036 [A0] Actualizar la memoria del proyecto (`MEMORY.md` y fichero de estado de la 010), revisar `git status` y commit sin `git add -A`; sin push. **Tras el merge a `main` y con confirmación**: X16 (sitio de Netlify con Albania y túnel cerrado y reabierto) en `docs/evidence/010/x16-netlify.md` **(memoria y commit hechos; sin marcar hasta cerrar X16 tras el merge)**

---

## Dependencias

- Setup → Foundational (T002 en la sesión principal; T003 a T009 en paralelo, ficheros distintos) → US3 (corrige el fallo real; MVP) → US1 → US2 → US4 → US5 → US6 → Polish.
- En US3: T010 (prueba primero) → T011 → T012; T013 (componente) es paralelo a T010–T012; T014 espera a T013 y a T004.
- En US1: T016 y T017 en paralelo (ficheros distintos); T018 espera a ambos y a T005 y T006; T019 y T024/T025 tocan `map.component.*`: van en orden T014 → T019 → T024 → T025.
- US2: T021 en paralelo con US1; T022 espera a T018 (mismo `app.component`) y a T021.
- US5: T028 antes de T029 (T029 usa la API del servicio); T030 espera a T029 e integra en `app.component`.
- T036 no puede cerrar X16 hasta el merge a `main`: se hace en una pasada posterior con confirmación.

## Ejemplos de ejecución en paralelo

- Tras T002: T003 a T009 (siete agentes pequeños de lógica pura, o dos agentes con varios ficheros cada uno sin solapes) mientras la sesión principal avanza con T010–T012 (API).
- T013, T016, T017 y T021 son componentes independientes: Sonnet en paralelo con la sesión principal en la API y el servicio.

## Estrategia

MVP: Phase 1–3 (el arreglo de la API con su prueba, la tolerancia del panel y el aviso de «sin eventos»), que corrige el fallo real. Después la distribución compacta, los avisos, el mapa, el botón de tema y la verificación de no regresión.
Una historia por sesión si se agota el contexto.

## Resumen

36 tareas: Setup 1, Foundational 8, US3 6, US1 5, US2 3, US4 4, US5 3, US6 3, Polish 3.
