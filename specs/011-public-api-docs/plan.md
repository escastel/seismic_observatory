# Implementation Plan: Documentación interactiva de la API en el dominio público

**Branch**: `011-public-api-docs` | **Date**: 2026-11-18 | **Spec**: `spec.md`

**Input**: Feature specification from `/specs/011-public-api-docs/spec.md`

## Summary

El dominio público de ngrok pasa a servir, además de `/api/*`, una **documentación interactiva** (Swagger UI) en `/docs`, con la descripción de los endpoints, ejemplos, errores y la nota de procedencia de los datos, y un modo «Probar»
que funciona a través de la página intermedia de ngrok (la interfaz añade la cabecera `ngrok-skip-browser-warning` a cada petición). La raíz `/` redirige a `/docs`. Se **revierte de forma justificada la decisión R7 de la 006** (que
desactivó `/docs` y `/redoc`) con tres medidas compensatorias: recursos de la interfaz de **versión exacta con integridad (SRI)**, un **límite de peticiones por visitante en el túnel** (política de tráfico de ngrok, con respuesta 429 en
español) y la declaración de lo que ve el navegador del visitante. La API no cambia de contrato: solo se enriquecen los metadatos de OpenAPI (descripciones, ejemplos, respuestas de error) y se añaden dos rutas de interfaz fuera del contrato.

## Technical Context

**Language/Version**: Python 3.11 + FastAPI 0.115.6 (`api/`); YAML de política de tráfico de ngrok; Docker Compose.

**Primary Dependencies**: **ninguna nueva en Python**. Interfaz: `swagger-ui-dist` **5.17.14** (Apache-2.0) cargada desde `cdn.jsdelivr.net` con `integrity` SRI (sha384) y versión exacta; no se vendoriza en el repositorio
(ver research R2). Imagen de ngrok ya fijada (`ngrok/ngrok:3.39.13-alpine`).

**Storage**: N/A.

**Testing**: pytest en el contenedor `tests` (`tests/query_api/`, nuevo `test_public_docs.py`): rutas `/docs` y `/`, contrato de OpenAPI sin cambios, metadatos, ausencia de rutas de escritura. Verificación real con Chrome
(Puppeteer) en local y por el túnel, y el inspector de ngrok para el límite. `tests/db` no se toca.

**Target Platform**: API local en Docker detrás del túnel `tunnel` de Compose (perfil `tunnel`); navegadores de escritorio y móvil.

**Project Type**: web-service (cambio acotado en `api/` y en el servicio `tunnel` de `compose.yaml`).

**Performance Goals**: la documentación carga en unos segundos en un navegador normal; `/api/*` sin sobrecoste apreciable (el límite lo aplica ngrok antes de llegar a la API).

**Constraints**: el plan gratuito de ngrok tiene topes de cuenta que condicionan el diseño: **1 GB de salida al mes** (215 MB usados) y **100 conexiones por minuto** en total (research R3). Por eso los recursos pesados de la interfaz
(1,4 MB de JavaScript) no pasan por el túnel y el límite por visitante es bajo (60 peticiones por minuto). Sin secretos en Git; ngrok nunca dentro del proceso de la API; texto en español, código en inglés; LF.

**Scale/Scope**: un puñado de visitantes externos (compañeros, profesor, evaluadores); tres endpoints de solo lectura.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / límite | Estado | Cómo se cumple |
|---|---|---|
| I. Superficie mínima («solo la API se expone»; Kafka y PostgreSQL nunca) | **Desviación justificada** | Se publica una ruta de interfaz más (`/docs`) y una redirección en `/`, ambas dentro de la API. No se expone nada más; sigue sin haber rutas de escritura ni de administración. Ver Complejidad. |
| VIII. Contrato de la API como fuente de verdad; CORS | Cumple | Los tres endpoints no cambian (prueba de contrato). CORS no cambia: la documentación es del mismo origen y la cabecera `ngrok-skip-browser-warning` ya está permitida. |
| IX. Evidencia ejecutada | Cumple | `docs/evidence/011/` con esperado/observado por escenario; una prueba no está superada hasta que hay evidencia. |
| Stack: ngrok como contenedor adicional, nunca en el proceso de la API | Cumple | La política de tráfico se monta en el servicio `tunnel`; la API no sabe de ngrok. |
| Stack: una biblioteca nueva solo si resuelve un requisito y queda fijada | Cumple | `swagger-ui-dist` 5.17.14 con SRI resuelve la documentación interactiva pedida; no entra en `requirements` ni en `package.json`. |
| Secretos fuera de Git | Cumple | La política (`tunnel/traffic-policy.yml`) no contiene claves; el authtoken sigue en `.env`. |
| Idioma y repositorio público | Cumple | Textos y documentación en español; identificadores en inglés. |

**Post-diseño**: sin cambios; la única desviación (superficie) queda registrada en Complejidad y se documentará en `docs/report.md`.

## Project Structure

### Documentation (this feature)

```text
specs/011-public-api-docs/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── public-surface.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
api/app/
├── main.py              # + metadatos de OpenAPI, GET /docs y GET / (fuera del contrato)
└── docs.py              # NUEVO: página de la documentación (HTML) y descripción en español
tunnel/
└── traffic-policy.yml   # NUEVO: límite de peticiones por visitante y respuesta 429
compose.yaml             # servicio tunnel: monta la política y usa --traffic-policy-file
tests/query_api/
└── test_public_docs.py  # NUEVO
docs/report.md, README.md, docs/evidence/011/
```

**Structure Decision**: la documentación vive en la API (comprobable con pytest y sin depender de la configuración del túnel); el túnel solo aplica el límite. La redirección de `/` vive también en la API por la misma razón.

## Complexity Tracking

| Violación | Por qué es necesaria | Alternativa más simple descartada |
|-----------|----------------------|-----------------------------------|
| Principio I («superficie mínima»): se publica `/docs` y una redirección en `/` (revierte R7 de la 006) | La persona autora quiere que personas externas puedan leer y probar la API desde el dominio público | No publicar nada (estado actual: el visitante ve un 404 y no sabe usar la API); compensado con límite por visitante, recursos de versión exacta con SRI, ausencia de escritura y declaración de lo que ve el navegador |
