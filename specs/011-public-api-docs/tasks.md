---

description: "Task list for feature 011: interactive API documentation on the public ngrok domain"
---

# Tasks: Documentación interactiva de la API en el dominio público

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/public-surface.md](contracts/public-surface.md), [quickstart.md](quickstart.md)

**Tests**: incluidas (FR-014, FR-015, principio IX). pytest en `tests/query_api/test_public_docs.py` (comportamiento: códigos, cabeceras, contenido, contrato) escrito **antes** de implementar y comprobando que falla;
lo visual y lo que pasa por el túnel se comprueba en el navegador real y con el inspector de ngrok (quickstart Z1 a Z13).

**Reglas**: código, nombres y comentarios en inglés; textos visibles y documentación en español. LF. Nunca leer ni imprimir `.env`; no ejecutar `docker compose config`. Sin dependencias nuevas (ni Python ni npm).
**No se cambian** los tres endpoints de datos (rutas, métodos, parámetros, tipos, valores por defecto, CORS, base de datos, consumidor, productor, panel). La API solo cambia en `api/app/main.py` y los ficheros nuevos
`api/app/docs.py` y `api/app/openapi_text.py`. `docker compose down -v`, `git push`, el PR y el merge piden confirmación explícita. Nunca dos ejecuciones de `tests/db` a la vez (no se tocan); `tests/query_api` comparte
`observatory_test`: una sola ejecución a la vez. Los scripts largos se escriben con la herramienta Write, no con heredocs.

**Agentes** (etiqueta `[A#]`, norma «Orquestación de agentes» de `CLAUDE.md`):

- `[A0]` sesión principal: `api/app/docs.py`, `api/app/main.py`, `compose.yaml`, la política del túnel, todo lo que toca Docker, ngrok y el navegador, evidencias, memoria y commit.
- `[A1]` agente nuevo en segundo plano, **Sonnet**: pruebas pytest (T002) y texto de los metadatos de OpenAPI (T003); solo sus ficheros, sin commit, sin ejecutar `tests/query_api` (la suite la ejecuta la sesión principal una vez).
- `[A2]` agente nuevo en segundo plano, **Haiku**: README de la evidencia a partir de lo ya guardado (nunca inventa cifras).

Cada agente recibe un prompt corto que apunta a este fichero y a los contratos (nunca `fork`).

## Format: `[ID] [P?] [Story] [A#] Descripción con ficheros`

---

## Phase 1: Setup

- [X] T001 [A0] Comprobar la rama `011-public-api-docs` y `.specify/feature.json`; guardar en `docs/evidence/011/00-environment.md` el estado «antes»: `GET /docs` y `GET /` dan 404 en local (`http://127.0.0.1:8000`) y por el dominio público, `GET /api/openapi.json` da 200, `pytest tests/query_api` (una sola vez, contenedor `tests`: `docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m pytest tests/query_api -q`) da 79 en verde, y los límites de ngrok de la cuenta (salida mensual usada, 100 conexiones por minuto)

---

## Phase 2: Foundational (bloquea las historias)

- [X] T002 [P] [A1] **Pruebas primero**: crear `tests/query_api/test_public_docs.py` con pruebas de comportamiento sobre el cliente ASGI de `tests/query_api/conftest.py` (`api.get`, `api.request`): (a) `GET /docs` → 200, `content-type` HTML, y su HTML referencia `swagger-ui-dist@5.17.14` (JavaScript y CSS) con atributo `integrity` que empieza por `sha384-` y `crossorigin="anonymous"`, y ningún recurso con versión flotante (`@5/`); lleva `Content-Security-Policy`; (b) `GET /` → redirección (307 o 302) con `location` terminado en `/docs` y sin cuerpo de error; `GET /otra-cosa` → 404 explícito; `GET /redoc` → 404; (c) `/docs` y `/` no aparecen en `paths` de `GET /api/openapi.json`; (d) **contrato intacto**: los `paths` de OpenAPI son exactamente `/api/eventos`, `/api/estadisticas` y `/api/salud`, todos solo con `get`, y los nombres de parámetros de `/api/eventos` son `mode, start, end, min_mag, country_id, exclude_synthetic, limit, offset` y de `/api/estadisticas` los de `common_filters` (leer `api/app/main.py` y `tests/query_api/test_statistics.py` para los nombres reales; no inventar); (e) **documentación útil**: la descripción general contiene la nota de procedencia («USGS», «no es una predicción» y «evaluación de riesgo») y el límite de 60 peticiones por minuto; cada operación tiene `summary` y `description` no vacíos; cada parámetro tiene `description`; `/api/eventos` y `/api/estadisticas` documentan 200, 422, 503 y 500, y `/api/salud` documenta 200 y 500 (siempre responde 200, «degraded» si falla un pool); (f) sin operaciones de escritura (`post`, `put`, `patch`, `delete`) y `POST /api/eventos` → 405; (g) CORS no cambia: `OPTIONS /api/eventos` con `Origin: https://observatorio.netlify.app` sigue permitiendo `GET` y la cabecera `ngrok-skip-browser-warning` y un origen no listado no recibe `access-control-allow-origin`. Solo `tests/query_api/test_public_docs.py`; ejecutar solo `docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m pytest tests/query_api/test_public_docs.py -q` y **no** la suite completa
- [X] T003 [P] [A1] Crear `api/app/openapi_text.py` (solo constantes, sin importar FastAPI): `API_TITLE`, `API_DESCRIPTION` (Markdown en español: qué es el servicio; datos sísmicos de USGS procesados por el proyecto; **no es una predicción ni una evaluación de riesgo**; solo lectura; límite de **60 peticiones por minuto por visitante** con respuesta 429; la primera visita desde un navegador a un dominio gratuito de ngrok muestra una página intermedia; «Probar» ya envía la cabecera que la evita; el navegador se conecta a `cdn.jsdelivr.net`, que ve su dirección IP y el `Referer`), `TAGS` (lista de `{name, description}`), por operación (`eventos`, `estadisticas`, `salud`) `summary` y `description`, por parámetro una `description` y un `example` coherentes con `specs/006-query-api/contracts/api.md` (inicio inclusivo y fin exclusivo, últimas 24 horas por defecto, `limit` máximo y 422 por más de 10.000 ventanas horarias en estadísticas), y los ejemplos de respuesta 200, 422 (`{"error":"invalid_parameters","detail":[{"param":"min_mag","message":"…"}]}`), 503 (`{"error":"database_unavailable",…}`) y 500 en el formato real que producen los manejadores de `api/app/main.py` (leerlos y copiar la forma exacta). Solo ese fichero. Sin tocar el contrato: no inventar campos ni parámetros

**Checkpoint**: pruebas escritas y texto listo; la implementación aún no existe.

- [X] T004 [A0] Ejecutar `test_public_docs.py` (T002) y comprobar que **falla** donde debe (docs, raíz, metadatos) y que pasan las de contrato y CORS (`docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m pytest tests/query_api/test_public_docs.py -q`); guardar la salida en `docs/evidence/011/z7-tests-first.md`

---

## Phase 3: User Story 1 - Probar la API desde el navegador (Priority: P1) 🎯 MVP

**Goal**: `/docs` con «Probar» que funciona desde el dominio público.

**Independent Test**: Z1, Z3, Z4 y Z5.

- [X] T005 [US1] [A0] Crear `api/app/docs.py`: constantes `SWAGGER_UI_VERSION = "5.17.14"`, URL y `integrity` de `swagger-ui-bundle.js` (`sha384-wmyclcVGX/WhUkdkATwhaK1X1JtiNrr2EoYJ+diV3vj4v6OC5yCeSu+yW13SYJep`) y de `swagger-ui.css` (`sha384-wxLW6kwyHktdDGr6Pv1zgm/VGJh99lfUbzSn6HNHBENZlCN7W602k9VkGdxuFvPn`) desde `https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/`, con `crossorigin="anonymous"`; función `docs_page(openapi_url) -> str` que devuelve el HTML (título «Observatorio Sísmico · API», `lang="es"`, aviso visible de qué dominio externo se carga y qué ve) e inicializa `SwaggerUIBundle` con `url` del contrato, `supportedSubmitMethods: ["get"]`, `deepLinking`, `docExpansion: "list"` y un `requestInterceptor` que añade `ngrok-skip-browser-warning: true` a cada petición (research R1); y `CSP` con `default-src 'none'`, `script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'`, `style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'`, `img-src 'self' data: https://cdn.jsdelivr.net`, `connect-src 'self'`
- [X] T006 [US1] [A0] En `api/app/main.py`: ruta `GET /docs` (`include_in_schema=False`) que devuelve `HTMLResponse(docs_page(...))` con `Content-Security-Policy`; **no** reactivar `/redoc` ni el `docs_url` de FastAPI. Reconstruir con `docker compose up --build -d api` y ejecutar las pruebas de `/docs` hasta que pasen
- [X] T007 [US1] [A0] Verificar Z1, Z3 y Z5 en navegador real (Chrome con Puppeteer, `http://127.0.0.1:8000/docs`): la página carga con los tres endpoints, `GET /api/salud` y `GET /api/eventos?min_mag=5` muestran la respuesta real y `GET /api/eventos?min_mag=abc` muestra el 422 con parámetro y motivo; capturas y datos en `docs/evidence/011/z1-z5-docs-local.md`
- [X] T008 [US1] [A0] Verificar Z4 por el dominio público (`https://modular-guidance-daybreak.ngrok-free.dev/docs`; el túnel ya corre): superar la página intermedia como lo haría una persona (en Puppeteer, con el botón «Visit Site» o la cookie), ejecutar `GET /api/salud` y `GET /api/eventos?min_mag=5` desde «Probar» y comprobar que llega el JSON real (no la página intermedia) y que no hay errores de CORS; capturas en `docs/evidence/011/z4-docs-public.md`

**Checkpoint**: US1 verificable por sí sola.

---

## Phase 4: User Story 2 - La raíz del dominio ya no da error (Priority: P1)

**Independent Test**: Z2.

- [X] T009 [US2] [A0] En `api/app/main.py`: ruta `GET /` (`include_in_schema=False`) que responde con una redirección temporal a `/docs` (misma ruta relativa, válida detrás del túnel); cualquier otra ruta inexistente sigue en 404. Reconstruir y ejecutar las pruebas de la raíz hasta que pasen
- [X] T010 [US2] [A0] Verificar Z2 con `curl -i` en local y por el dominio público, y en navegador: `/` termina en la documentación, `/otra-cosa` sigue dando 404; guardar en `docs/evidence/011/z2-root.md`

---

## Phase 5: User Story 3 - Documentación comprensible (Priority: P2)

**Independent Test**: Z6 y la prueba de metadatos.

- [X] T011 [US3] [A0] Integrar `api/app/openapi_text.py` (T003) en `api/app/main.py`: `FastAPI(title=…, description=…, openapi_tags=…)`, `summary`, `description`, `responses` (422, 503 y 500; `/api/salud` solo 200 y 500) y `examples` en `@app.get(...)` y en los `Query(...)` de `common_filters`, `events` y `statistics`, **sin cambiar** nombres, tipos, valores por defecto, rangos ni validaciones; reconstruir y ejecutar `test_public_docs.py` completo (contrato intacto y metadatos) hasta que pasen
- [X] T012 [US3] [A0] Verificar Z6: una persona sin contexto (el agente Sonnet de T013, sin ver el código) obtiene «eventos de magnitud ≥ 5 de las últimas 24 horas» solo con el HTML y el `openapi.json` de `/docs` y lo anota; medir el tiempo y guardar en `docs/evidence/011/z6-useful-docs.md`. Revisar capturas de la descripción general (nota de procedencia visible) en ambos temas del navegador
- [X] T013 [P] [US3] [A1] Prompt corto para el agente que hace de «persona sin contexto» de T012: leer solo `GET /api/openapi.json` y el texto de `/docs` (guardados por A0 en el directorio temporal), sin el repositorio, y escribir los pasos exactos que seguiría para obtener los eventos de magnitud ≥ 5 de las últimas 24 horas y cualquier duda; no toca ficheros del repositorio

---

## Phase 6: User Story 4 - Proteger la API del abuso (Priority: P2)

**Independent Test**: Z9.

- [X] T014 [US4] [A0] Crear `tunnel/traffic-policy.yml` con la política validada en research R4: regla `per-visitor-rate-limit` (`rate-limit`, `sliding_window`, capacidad 60, `rate: 60s`, `bucket_key: [conn.client_ip]`) y regla `too-many-requests` (`expressions: [actions.ngrok.rate_limit.limited]`, `custom-response` 429, `content-type: application/json`, `retry-after: "60"`, cuerpo `{"error":"too_many_requests","message":"Demasiadas peticiones. Espera un minuto antes de volver a probar."}`), **sin** `access-control-allow-origin`; validarla con la herramienta de ngrok (`gw_validate_traffic_policy`) y guardar el resultado en `docs/evidence/011/z9-policy-validation.md`
- [X] T015 [US4] [A0] En `compose.yaml` (servicio `tunnel`): montar `./tunnel/traffic-policy.yml:/etc/ngrok/traffic-policy.yml:ro` y añadir `--traffic-policy-file /etc/ngrok/traffic-policy.yml` al `command`; sin secretos nuevos (el authtoken y el dominio siguen en `.env`). Reiniciar solo ese servicio (`docker compose --profile tunnel up -d tunnel`) y comprobar en el registro que el agente arranca sin error de política y que el dominio sigue sirviendo `/api/salud`
- [X] T016 [US4] [A0] Verificar Z9 por el dominio público con **una sola conexión persistente** (la cuenta gratuita admite 100 conexiones por minuto en total): ráfaga de 300 peticiones a `/api/salud` en un minuto desde este equipo con la cabecera de omisión; esperado: las primeras ≈ 60 devuelven 200 y el resto 429 con el cuerpo en español y `Retry-After: 60`; el inspector de ngrok (`gw_query_traffic_inspector`, agrupado por estado y por IP) lo confirma; pasado un minuto vuelve a responder 200; en paralelo, la API local (`http://127.0.0.1:8000`) responde con normalidad (no pasa por el túnel). Si no hay un segundo origen disponible, dejar «otro origen: no comprobado» en la evidencia. Guardar en `docs/evidence/011/z9-rate-limit.md`. Aviso: esta prueba limita temporalmente la IP del equipo en el dominio público (también al panel de Netlify abierto aquí)
- [X] T017 [US4] [A0] Comprobar que el uso normal del panel no se limita: abrir el panel (config real) durante 5 minutos con refresco de 60 s y confirmar con el inspector que no hay ningún 429 y que el total de peticiones por visitante queda muy por debajo de 60 por minuto; guardar en `docs/evidence/011/z9-panel-not-limited.md`

---

## Phase 7: User Story 5 - No se rompe lo que ya funciona (Priority: P1)

**Independent Test**: Z7, Z8, Z10, Z11.

- [X] T018 [US5] [A0] Z7 y Z8: ejecutar `pytest tests/query_api` completa **una sola vez** (las 79 anteriores más las nuevas), y por el dominio público probar `POST /api/eventos`, `PUT`, `DELETE`, `/redoc`, `/admin`, `/metrics`, `/docs/oauth2-redirect`: 404 o 405; confirmar que el contrato no tiene operaciones de escritura. `git diff origin/main` de `frontend/`, `consumer/`, `producer/`, `db/` y `common/` vacío; los endpoints de datos sin cambios de comportamiento. Guardar en `docs/evidence/011/z7-z8-regression.md`
- [X] T019 [US5] [A0] Z10: abrir el panel de Netlify (`https://seismicobservatoryecr.netlify.app/`), filtrar por Albania y por otro país, cerrar y reabrir el túnel (con la política activa) y comprobar la recuperación sin recargar y sin errores de CORS; guardar en `docs/evidence/011/z10-netlify.md`. Nota: pide que la rama esté desplegada o que el panel de Netlify siga siendo el de `main` (la feature no toca el frontend)
- [X] T020 [US5] [A0] Z11 y Z12: inspeccionar en el navegador los recursos de `/docs` (versión exacta con `integrity`; dominios externos: solo `cdn.jsdelivr.net`), la cabecera CSP, que un `integrity` alterado impide cargar el script (prueba de comportamiento con una copia local de la página y un hash incorrecto), y axe-core (WCAG A y AA) sobre `/docs`, anotando las excepciones atribuibles a la interfaz de Swagger si las hay; guardar en `docs/evidence/011/z11-z12-resources-a11y.md`

---

## Phase 8: Polish y cierre

- [X] T021 [P] [A2] Con la evidencia de `docs/evidence/011/`, redactar `docs/evidence/011/README.md` (resumen de Z1 a Z13 con esperado/observado, estado y capturas enlazadas) sin inventar cifras
- [X] T022 [A0] Actualizar `docs/report.md` (apartado nuevo «Documentación pública de la API (spec 011)»: qué se publica, la **reversión justificada de R7** y sus medidas compensatorias, el límite de 60 peticiones por minuto, la declaración de recursos externos —`cdn.jsdelivr.net` ve la IP y el `Referer`—, la página intermedia de ngrok y los topes del plan gratuito) y `README.md` (cómo abrir `/docs` en local y por el dominio público; `tunnel/traffic-policy.yml`); revisar enlaces
- [X] T023 [A0] Actualizar la memoria del proyecto (`MEMORY.md` y fichero de estado de la 011), revisar `git status` y commit sin `git add -A`; sin push; restaurar `frontend/public/config.json` si se tocó (`git diff` vacío). El push, el PR y el merge piden confirmación

---

## Dependencias

- Setup → Foundational (T002 y T003 en paralelo, ficheros distintos) → T004 → US1 (MVP) → US2 → US3 → US4 → US5 → Polish.
- `api/app/main.py` lo tocan T006, T009 y T011: van en orden y en la sesión principal.
- US4 reinicia el túnel (`tunnel`): hacerlo después de US1 y US2 para que Z4 y Z2 se verifiquen primero sin límite; Z9 y Z10 con la política activa.
- T012 espera a T011 y a T013.

## Ejemplos de ejecución en paralelo

- Tras T001: T002 (pruebas) y T003 (texto de OpenAPI) a la vez, dos agentes Sonnet con ficheros distintos, mientras la sesión principal escribe `api/app/docs.py` (T005).
- T013 (la «persona sin contexto») en paralelo con T014 y T015.

## Estrategia

MVP: Fases 1 a 3 (`/docs` con «Probar» funcionando por el dominio público) y la raíz de la Fase 4. Después los metadatos útiles, el límite de peticiones y la verificación de no regresión. Una historia por sesión si se agota el contexto.

## Resumen

23 tareas: Setup 1, Foundational 3, US1 4, US2 2, US3 3, US4 4, US5 3, Polish 3.
