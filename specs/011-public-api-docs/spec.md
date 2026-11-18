# Feature Specification: Documentación interactiva de la API en el dominio público

**Feature Branch**: `011-public-api-docs`

**Created**: 2026-11-18

**Status**: Draft

**Input**: User description: "Spec 011: que el dominio público de ngrok (`https://modular-guidance-daybreak.ngrok-free.dev`) muestre un panel de pruebas de la API, al estilo del Swagger de FastAPI, con la documentación de la API, donde personas externas puedan consultar y probar los endpoints. Hoy la raíz del dominio devuelve `{"detail":"Not Found"}`."

**Depende de**: `specs/006-query-api` (contrato HTTP, fuente de verdad: no se modifica; su decisión R7 de desactivar `/docs` y `/redoc` se **revierte de forma justificada** aquí) y `specs/007-angular-dashboard` (el panel de Netlify consume la misma API y no debe romperse). Parte de `main`.

## Contexto y decisión que se revierte

El túnel de ngrok reenvía todo el tráfico del dominio a la API de consulta. La API solo expone `GET /api/eventos`, `GET /api/estadisticas` y `GET /api/salud` (solo lectura) y su contrato legible por máquinas en `/api/openapi.json`. En la spec 006 (decisión R7) se desactivaron las páginas de documentación interactiva `/docs` y `/redoc` por dos motivos: **superficie mínima** (principio I de la constitución) y porque esas páginas cargaban recursos de un CDN con versión flotante y no formaban parte del contrato.

Esta spec cambia esa decisión a petición de la persona autora: quien reciba la dirección pública debe poder **leer cómo se usa la API y probarla** sin instalar nada. La decisión de R7 queda registrada como revertida, con este motivo, y se compensa con un límite de peticiones, recursos de interfaz de versión exacta y una declaración de lo que ve el navegador del visitante. Lo que **no** cambia: la API sigue siendo de solo lectura, no se publica nada más por el túnel (Kafka y PostgreSQL nunca), no hay secretos y el contrato de los endpoints existentes queda intacto.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Probar la API desde el navegador (Priority: P1)

Una persona externa (un compañero, el profesor, un evaluador) abre la dirección pública, ve la documentación interactiva de la API, elige un endpoint, rellena parámetros y pulsa «Probar» para ver la respuesta real, sin herramientas adicionales.

**Why this priority**: es el objetivo de la feature: documentar y poder probar la API desde el dominio público.

**Independent Test**: abrir `https://modular-guidance-daybreak.ngrok-free.dev/docs` en un navegador sin sesión, ejecutar `GET /api/salud` y `GET /api/eventos` con un filtro y comprobar que la respuesta mostrada es la real.

**Acceptance Scenarios**:

1. **Given** el túnel y la API en marcha, **When** una persona abre la ruta de documentación del dominio público, **Then** ve la lista de los tres endpoints con su descripción y puede desplegar cada uno.
2. **Given** la documentación abierta en el dominio público, **When** pulsa «Probar» en `GET /api/eventos` con `min_mag=5`, **Then** recibe la respuesta real de la API (código, cabeceras y cuerpo) en la misma página, sin errores de red ni de CORS, incluso con la página intermedia que ngrok muestra en dominios gratuitos.
3. **Given** una consulta con un parámetro no válido, **When** la persona la ejecuta, **Then** ve el error explícito de la API (422 con el parámetro y el motivo) y no una página en blanco.
4. **Given** la documentación abierta, **When** se intenta usar cualquier método distinto de lectura, **Then** no existe ninguna operación de escritura que probar.

---

### User Story 2 - La raíz del dominio ya no da error (Priority: P1)

Quien abre la dirección pública sin ruta (`/`) hoy ve `{"detail":"Not Found"}`. Debe llegar a la documentación (o a una portada que enlace a ella y al panel).

**Why this priority**: es la queja concreta que origina la feature; sin esto, el visitante piensa que el servicio está roto.

**Independent Test**: abrir el dominio sin ruta y comprobar que ya no aparece un 404 y que se llega a la documentación en un solo paso.

**Acceptance Scenarios**:

1. **Given** el dominio público, **When** se abre `/`, **Then** se llega a la documentación interactiva (por redirección o por una portada con un enlace evidente), sin respuesta de error.
2. **Given** la raíz con una portada, **When** se lee, **Then** enlaza al panel de Netlify y a la documentación y dice en español qué es el servicio (datos sísmicos de USGS procesados por el proyecto, solo lectura).
3. **Given** una ruta que no existe (`/otra-cosa`), **When** se abre, **Then** la respuesta sigue siendo un 404 explícito (no se convierte en documentación).

---

### User Story 3 - Documentación comprensible para quien no conoce el proyecto (Priority: P2)

Cada endpoint explica para qué sirve, qué parámetros admite (con valores por defecto, rangos y ejemplos), qué devuelve (con un ejemplo de respuesta) y qué errores puede dar. Una nota visible aclara que los datos son de USGS procesados por el proyecto y que no son una predicción ni una evaluación de riesgo.

**Why this priority**: sin una documentación clara, el panel de pruebas es un listado de nombres; con ella una persona nueva consigue su primera consulta sola.

**Independent Test**: una persona que no conoce el proyecto obtiene los eventos de magnitud 5 o más de las últimas 24 horas leyendo solo la documentación.

**Acceptance Scenarios**:

1. **Given** la documentación, **When** se despliega `GET /api/eventos`, **Then** se describen `mode`, `start`, `end`, `min_mag`, `country_id`, `limit` y `offset` con su significado (inicio inclusivo, fin exclusivo, últimas 24 horas por defecto, límite máximo) y hay un ejemplo de respuesta.
2. **Given** la documentación de `GET /api/estadisticas` y `GET /api/salud`, **When** se leen, **Then** cada una explica su contenido y las respuestas y errores posibles (200, 422, 503, 500).
3. **Given** cualquier página de documentación, **When** se abre, **Then** aparece la nota de procedencia y limitación de los datos, en español.
4. **Given** el contrato publicado (`/api/openapi.json`), **When** se compara con los endpoints reales, **Then** coincide con ellos y no se añade ninguna ruta ni campo nuevo.

---

### User Story 4 - Proteger la API del abuso de visitantes externos (Priority: P2)

Al hacer pública la documentación aumenta el tráfico no controlado. Un visitante que lance muchas peticiones seguidas recibe una respuesta clara de «demasiadas peticiones» sin degradar el servicio para los demás ni para el panel.

**Why this priority**: la API la sirve un portátil con una base de datos local; sin límite, unas pocas personas o un bucle pueden saturarla.

**Independent Test**: lanzar una ráfaga de peticiones desde un mismo origen hasta ser limitado y comprobar que, en paralelo, el panel y otra dirección siguen recibiendo respuesta normal.

**Acceptance Scenarios**:

1. **Given** el uso normal del panel (unas pocas peticiones por minuto), **When** se usa durante una sesión larga, **Then** nunca recibe una respuesta de límite.
2. **Given** un visitante que supera el límite, **When** envía más peticiones, **Then** recibe un 429 con un mensaje en español y el tiempo de espera sugerido, y las peticiones por debajo del límite siguen respondiendo.
3. **Given** que el límite está activo, **When** el panel de Netlify consulta la API, **Then** el contrato, las rutas `/api/*` y los encabezados CORS no cambian.

---

### User Story 5 - No se rompe lo que ya funciona (Priority: P1)

El panel publicado en Netlify, el contrato de la API, las pruebas existentes y las reglas de la constitución siguen cumpliéndose tras publicar la documentación.

**Why this priority**: es un cambio en la superficie pública de un sistema ya verificado.

**Independent Test**: el panel de Netlify carga, filtra y se recupera tras cerrar y reabrir el túnel igual que antes; las pruebas de la API siguen en verde; por el túnel solo se alcanzan la API y su documentación.

**Acceptance Scenarios**:

1. **Given** la documentación publicada, **When** se abre el panel de Netlify, **Then** carga y filtra igual que antes, sin errores de CORS.
2. **Given** el túnel, **When** se enumeran las rutas accesibles desde fuera, **Then** son solo `/api/*`, la documentación y la raíz; Kafka y PostgreSQL no son alcanzables.
3. **Given** el repositorio, **When** se revisa, **Then** la decisión R7 consta como revertida con su motivo y `docs/report.md` describe la documentación pública, el límite y lo que ve el navegador del visitante.

---

### Edge Cases

- **Primera visita desde un navegador a un dominio gratuito de ngrok**: aparece una página intermedia de ngrok antes de la documentación; no se puede quitar y debe quedar documentada. «Probar» desde la página de documentación debe funcionar igualmente.
- **Visitante sin salida a Internet hacia los recursos de la interfaz**: si algún recurso externo no carga, la documentación debe seguir mostrando al menos el contrato y un aviso claro (los recursos son de versión exacta o los sirve el propio proyecto).
- **La base de datos no está disponible**: «Probar» muestra el 503 explícito de la API, nunca «0 eventos» como resultado válido.
- **Peticiones de los visitantes con periodos enormes**: la API ya responde 422 por más de 10.000 ventanas horarias; la documentación lo explica y no se relaja.
- **Rutas de documentación que no deben existir**: no se publica ninguna ruta de administración, de escritura ni de métricas internas.
- **Muchos visitantes detrás de la misma dirección** (aula, red de la universidad): el límite por visitante no debe bloquear de forma injusta a todos; el umbral debe dejar margen para varias personas.
- **Túnel parado**: la dirección no responde y el panel de Netlify muestra su aviso de backend inaccesible, como hasta ahora.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: La dirección pública MUST ofrecer una documentación interactiva de la API (lista de endpoints, parámetros, respuestas, errores) y un modo «Probar» que ejecute las peticiones contra la API real desde el propio dominio.
- **FR-002**: «Probar» MUST funcionar desde un navegador sin configuración previa, incluida la página intermedia de ngrok para dominios gratuitos, y sin errores de CORS.
- **FR-003**: La raíz del dominio MUST dejar de devolver un 404: MUST llevar a la documentación, o mostrar una portada en español con un enlace evidente a la documentación y al panel de Netlify. Las rutas inexistentes MUST seguir devolviendo 404.
- **FR-004**: La documentación MUST describir cada endpoint con su propósito, cada parámetro (significado, valor por defecto, rango, ejemplo), un ejemplo de respuesta correcta y los errores posibles (422, 503, 500), en español.
- **FR-005**: La documentación MUST mostrar una nota visible de procedencia y límite de los datos: datos sísmicos de USGS procesados por el proyecto, descriptivos, no una predicción ni una evaluación de riesgo.
- **FR-006**: El contrato publicado MUST coincidir con la API real y MUST NOT añadir rutas, campos ni operaciones de escritura. El contrato de la spec 006 no cambia.
- **FR-007**: La API MUST seguir siendo de solo lectura: ninguna operación de escritura, administración o métricas internas se publica por el túnel. Kafka y PostgreSQL MUST NOT ser alcanzables.
- **FR-008**: MUST existir un límite de peticiones por visitante en el dominio público: el uso normal del panel (unas pocas peticiones por minuto) nunca recibe el límite, y un visitante que lo supera recibe un 429 en español con el tiempo de espera sugerido, sin afectar a los demás visitantes.
- **FR-009**: El panel de Netlify, sus rutas `/api/*`, la política de CORS (origen exacto de Netlify y el de desarrollo, métodos GET y OPTIONS, cabecera `ngrok-skip-browser-warning`) y el contrato MUST permanecer sin cambios de comportamiento.
- **FR-010**: Los recursos de la interfaz de documentación MUST estar a versión exacta (no flotante) o servirse desde el propio proyecto, y MUST declararse (en `docs/report.md` y en la propia documentación) a qué dominios se conecta el navegador del visitante y qué ven esos servicios (dirección IP y cabecera de origen).
- **FR-011**: La configuración del túnel MUST vivir en el servicio de túnel de Compose (opcional, con su perfil) y MUST NOT ejecutarse dentro del proceso de la API; el límite de peticiones y la raíz se resuelven sin introducir secretos ni credenciales en Git.
- **FR-012**: Cualquier dependencia nueva MUST quedar fijada a versión exacta y justificada; si no es imprescindible, no se añade.
- **FR-013**: La decisión R7 de la spec 006 MUST registrarse como revertida, con el motivo y las medidas compensatorias (límite, versión exacta, declaración de recursos), en `docs/report.md` y en el plan de esta spec.
- **FR-014**: La verificación MUST hacerse con el sistema real (API local y por el túnel) con evidencia esperado/observado en `docs/evidence/011/`, incluida una prueba de comportamiento por cada requisito; una prueba no está superada hasta que hay evidencia.
- **FR-015**: Las pruebas existentes de la API (`tests/query_api`) MUST seguir en verde y las pruebas nuevas MUST comprobar comportamientos (códigos, cabeceras, contenido de las respuestas), no la presencia de texto en el código.

### Key Entities

- **Documentación interactiva**: página pública con la descripción de los endpoints, el modo «Probar» y la nota de procedencia de los datos.
- **Contrato publicado**: descripción legible por máquinas de los tres endpoints (`/api/openapi.json`), fuente de la documentación.
- **Portada o redirección de la raíz**: lo que ve quien abre el dominio sin ruta.
- **Límite de peticiones**: regla por visitante con un umbral, un tiempo de espera y un mensaje en español.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Una persona que abre la dirección pública llega a la documentación en un solo paso (cero respuestas de error en la raíz) en el 100 % de los intentos.
- **SC-002**: Una persona que no conoce el proyecto obtiene su primera consulta de eventos (magnitud mínima 5, últimas 24 horas) en menos de 2 minutos usando solo la documentación.
- **SC-003**: «Probar» devuelve la respuesta real de los tres endpoints desde el dominio público en el 100 % de los casos de la prueba, sin errores de CORS ni de red.
- **SC-004**: Tras publicar la documentación, el panel de Netlify supera las mismas comprobaciones que antes (carga, filtro, recuperación tras cerrar y reabrir el túnel) y las 79 pruebas de `tests/query_api` siguen en verde.
- **SC-005**: Con una ráfaga de 300 peticiones en un minuto desde un mismo origen, las peticiones por encima del umbral reciben un 429 en español, y mientras tanto otro origen y el panel reciben respuestas normales.
- **SC-006**: Por el túnel solo se alcanzan la raíz, la documentación y `/api/*`: el 100 % de las rutas de escritura, administración o métricas probadas devuelven 404 o 405.
- **SC-007**: La documentación declara el 100 % de los dominios externos a los que se conecta el navegador del visitante y todos los recursos de la interfaz están a versión exacta o servidos por el proyecto.

## Assumptions

- La documentación vive en la propia API de consulta (ruta `/docs`) y la raíz **redirige** a ella; la portada con enlaces al panel de Netlify es una alternativa que se decide en el plan si resulta más útil. El plan fija el reparto definitivo entre API y configuración del túnel.
- El límite se aplica **por dirección de origen** y se diseña con margen para varias personas detrás de la misma dirección; el plan lo fija en 60 peticiones por minuto por visitante porque el plan gratuito de ngrok limita toda la cuenta a 100 conexiones por minuto y a 1 GB de salida al mes.
- La página intermedia de ngrok en dominios gratuitos no se puede quitar y queda documentada; solo se garantiza que «Probar» funciona desde la documentación una vez dentro.
- Los datos son públicos de USGS procesados por el proyecto; no hay autenticación ni claves de API para los visitantes (CORS no es autenticación y no se presenta como tal).
- El contrato, los filtros, los códigos de error y los límites de la API de la spec 006 no cambian; las descripciones y ejemplos de la documentación son metadatos del contrato, no cambios de comportamiento.
- Los textos visibles y la documentación van en español; código, identificadores y ficheros en inglés. LF en todo el repositorio, también en Windows.
- Se trabaja en la rama `011-public-api-docs`, nunca directamente en `main`; el push, el PR y el merge piden confirmación explícita de la persona autora.
