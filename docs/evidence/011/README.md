# 011 · Documentación pública de la API: resumen de validación

Resultado de los escenarios Z1 a Z13 de la [guía de validación](../../../specs/011-public-api-docs/quickstart.md). Ejecución: 2026-11-18. Antes de la feature (ver [00-environment.md](00-environment.md)), `/docs` y la raíz daban 404 por el dominio público y `/api/openapi.json` daba 200.

| Escenario | Esperado | Observado | Estado | Evidencia y capturas |
|---|---|---|---|---|
| Z1 · Documentación local | `/docs` 200, título «Observatorio Sísmico · API», tres endpoints y nota de procedencia | 200; título correcto; `/api/eventos`, `/api/salud` y `/api/estadisticas`; aviso de `cdn.jsdelivr.net` visible | superado | [z1-z5-docs-local.md](z1-z5-docs-local.md); [overview](z1-local-1-overview.png); [descripción](z6-docs-description.png) |
| Z2 · Raíz | Redirección a `/docs` sin 404; `/otra-cosa` da 404 | Local y dominio público: 307 con `Location: /docs`; `/otra-cosa` 404; la raíz siguiendo redirecciones termina en `/docs` con 200 | superado | [z2-root.md](z2-root.md) |
| Z3 · Probar (local) | Respuesta real de `GET /api/salud` y `GET /api/eventos?min_mag=5` sin errores de red ni CORS | `status: ok`; `count 9, total 9` en modo `live`; ninguna petición fallida | superado | [z1-z5-docs-local.md](z1-z5-docs-local.md); [salud](z1-local-2-salud.png); [min_mag=5](z1-local-3-eventos-minmag5.png) |
| Z4 · Probar (dominio público) | Respuesta real tras la página intermedia, sin CORS | Página intermedia superada con «Visit Site»; `/docs` carga; «Probar» devuelve JSON real; `failedRequests: []` | superado | [z4-docs-public.md](z4-docs-public.md); [overview](z4-public-1-overview.png); [salud](z4-public-2-salud.png); [min_mag=5](z4-public-3-eventos-minmag5.png) |
| Z5 · Error explícito | 422 con parámetro y motivo | `limit=0` → `{"param":"limit","message":"must be between 1 and 1000"}`; `min_mag` no numérico (`5abc`) → 422 con `min_mag` | superado con limitaciones | [z1-z5-docs-local.md](z1-z5-docs-local.md); [limit=0](z1-local-4-eventos-422-limit0.png); [min_mag](z1-local-5-eventos-minmag-abc.png); [público](z4-public-4-eventos-422-limit0.png) |
| Z6 · Documentación útil | Eventos M ≥ 5 de las últimas 24 h solo con `/docs`, en menos de 2 minutos | Agente sin contexto, con solo `openapi.json` y el HTML de `/docs`, obtuvo `GET /api/eventos?min_mag=5` en unos 7 s | superado con limitaciones | [z6-useful-docs.md](z6-useful-docs.md); [descripción](z6-docs-description.png) |
| Z7 · Contrato intacto | `pytest tests/query_api` en verde; contrato igual que la 006 | 99 passed en 38,04 s (79 anteriores + 20 nuevas); rutas y parámetros sin cambios; `git diff origin/main` vacío en `frontend/`, `consumer/`, `producer/`, `db/` y `common/` | superado | [z7-tests-first.md](z7-tests-first.md); [z7-z8-regression.md](z7-z8-regression.md) |
| Z8 · Solo lectura | `POST`, `PUT`, `DELETE`, `/redoc`, `/admin`, `/metrics` dan 404 o 405 | 405 en `POST`, `PUT`, `PATCH` y `DELETE` de `/api/eventos`; 404 en `/redoc`, `/admin`, `/metrics` y otras rutas; el contrato solo tiene tres rutas, todas `get` | superado | [z7-z8-regression.md](z7-z8-regression.md) |
| Z9 · Límite de peticiones | Más de 60 por minuto → 429 en español con `Retry-After`; otro origen y el panel normales; inspector de ngrok lo confirma | Ráfaga de 300: 53 × 200 y 247 × 429 con `Retry-After: 60` y cuerpo JSON en español; inspector: 303 peticiones (53 × 200, 250 × 429); 200 al minuto; panel 5 min sin 429 (máximo 10 peticiones por minuto) | superado con limitaciones | [z9-rate-limit.md](z9-rate-limit.md); [z9-policy-validation.md](z9-policy-validation.md); [z9-panel-not-limited.md](z9-panel-not-limited.md); [panel](z9-panel.png) |
| Z10 · Panel intacto | Mismos resultados que la 010 y sin errores de CORS, con el túnel cerrado y reabierto | Albania: 0 eventos con aviso; Estados Unidos: 148; sin filtro: 197; túnel cerrado muestra la última lectura; reabierto recupera sin recargar; sin errores de API con el túnel abierto | superado con limitaciones | [z10-netlify.md](z10-netlify.md); [z10-netlify.json](z10-netlify.json); [carga](z10-1-load.png); [Albania](z10-2-Albania.png); [Estados Unidos](z10-3-Estados-Unidos.png); [túnel cerrado](z10-5-tunnel-closed.png); [túnel reabierto](z10-6-tunnel-reopened.png) |
| Z11 · Recursos exactos | `swagger-ui-dist@5.17.14` con `integrity`; solo `cdn.jsdelivr.net` como externo | Versión exacta con `sha384` y `crossorigin: anonymous`; CSP según el contrato; con el hash alterado no se dibuja nada | superado | [z11-z12-resources-a11y.md](z11-z12-resources-a11y.md); [z11-z12-report.json](z11-z12-report.json); [claro](z11-docs-light.png); [oscuro](z11-docs-dark.png); [integridad alterada](z11-tampered-integrity.png) |
| Z12 · Accesibilidad básica | Sin violaciones atribuibles a la página propia; excepciones documentadas | Vista cerrada: `color-contrast` y `nested-interactive` (graves); con una operación abierta, además `select-name`; todas en Swagger UI, aceptadas como excepciones; no cumple al 100 % WCAG AA | superado con limitaciones | [z11-z12-resources-a11y.md](z11-z12-resources-a11y.md); [claro](z11-docs-light.png); [oscuro](z11-docs-dark.png) |
| Z13 · Documentación declarada | `docs/report.md` recoge la reversión de R7, el límite, los recursos externos y la página intermedia | El apartado «Documentación pública de la API (spec 011)» recoge los cuatro puntos y enlaza este README | superado | [report.md](../../report.md#documentación-pública-de-la-api-spec-011) |

## Limitaciones

- Z5: `min_mag=abc` literal no se probó; la prueba equivalente fue `5abc`.
- Z6: lo hizo un agente simulado, no una persona real. El esquema de la respuesta 200 está vacío y no se aclara si `min_mag=5` incluye 5,0.
- Z9: el corte fue en 53 peticiones, no en 60 (ngrok aplica la ventana de forma aproximada). Tres respuestas 429 del inspector no se atribuyeron a ningún script. La primera política dio un 429 vacío de ngrok y se corrigió con `enforce: false`.
- Z10: un solo dispositivo; no se esperó el refresco automático de 60 s; 8 respuestas `400` de las teselas de OpenStreetMap no se investigaron.
- Z12 y Swagger UI: 2 violaciones graves y 1 crítica, aceptadas como excepciones de una librería de terceros con integridad fijada. Swagger UI no tiene tema oscuro.
- Linux: no se ha probado en el otro equipo.

## No comprobado

- Z9: un segundo origen distinto y la red del móvil.
- Z1: que el 404 de la consola corresponda a `/favicon.ico` en la petición concreta del navegador.
- Linux: toda la feature.
