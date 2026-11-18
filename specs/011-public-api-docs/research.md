# Investigación (Fase 0)

No quedan incógnitas. Comprobado el 2026-11-18 con el sistema real y las herramientas de ngrok.

## R1. La página intermedia de ngrok también afecta a «Probar»

- Con `curl` simulando un navegador (`User-Agent: Mozilla/5.0 …`, sin la cabecera de omisión) y `Accept: application/json`, el dominio devuelve **la página intermedia** (`200 text/plain`, «You are about to visit…»), no el JSON.
  Con `Accept: text/html` devuelve el HTML de la página.
- **Decisión**: la página de documentación añade `ngrok-skip-browser-warning: true` a **todas** las peticiones de «Probar» mediante el interceptor de peticiones de Swagger UI. Es del mismo origen, así que no hay CORS ni preflight.
- La primera visita a `/docs` desde un navegador seguirá mostrando la página intermedia de ngrok (no se puede quitar en un dominio gratuito): queda documentado.
- **Alternativa descartada**: pedir a los visitantes una extensión o un `User-Agent` propio.

## R2. Recursos de la interfaz: CDN con versión exacta y SRI, no servidos por el túnel

- FastAPI 0.115.6 genera la página con `swagger-ui-dist@5` (versión **flotante**) desde jsDelivr.
- **Decisión**: página propia con `swagger-ui-dist@5.17.14` y atributos `integrity` (sha384) calculados el 2026-11-18:
  - `swagger-ui-bundle.js`, 1.452.753 bytes, `sha384-wmyclcVGX/WhUkdkATwhaK1X1JtiNrr2EoYJ+diV3vj4v6OC5yCeSu+yW13SYJep`.
  - `swagger-ui.css`, 152.071 bytes, `sha384-wxLW6kwyHktdDGr6Pv1zgm/VGJh99lfUbzSn6HNHBENZlCN7W602k9VkGdxuFvPn`.
  - Con `crossorigin="anonymous"`: una versión alterada o distinta no se ejecuta.
- **Por qué no se sirven desde el propio proyecto**: el plan gratuito de ngrok limita la salida a **1 GB al mes** (215 MB usados el 2026-11-18); cada visita serviría ≈ 1,6 MB por el túnel y el tope es de la cuenta entera. Con el CDN ese tráfico no pasa por ngrok.
- **Coste**: el navegador del visitante se conecta a `cdn.jsdelivr.net`, que ve su dirección IP y el `Referer`. Se declara en la propia página y en `docs/report.md` (FR-010).
- **Alternativas descartadas**: vendorizar 1,6 MB en el repositorio y servirlos por el túnel (consume el tope de ancho de banda); usar la versión flotante `@5` (no reproducible y no verificable con SRI).
- `/docs` lleva una cabecera `Content-Security-Policy` que limita scripts y estilos a `'self'`, jsDelivr y el script de arranque de la propia página.

## R3. Topes del plan gratuito de ngrok que condicionan el límite

`platform_get_limits` (2026-11-18): salida **1.000.000.000 bytes al mes** (usados 215.493.603), **100 conexiones por minuto** en total (`ConnectionsToEndpointsPerMinute`, ERR_NGROK_715), 3 endpoints simultáneos,
15 reglas por política y 20 acciones por regla. Consecuencia: un límite de 120 peticiones por minuto por visitante no protegería la cuenta; se fija **60 peticiones por minuto por visitante**. El uso normal del panel son
unas 3 peticiones por minuto (estadísticas, eventos y salud cada 60 s).

## R4. Límite de peticiones: política de tráfico en el túnel

- Acción `rate-limit` (algoritmo `sliding_window`, ventana de 60 s, el mínimo permitido) con clave `conn.client_ip`, y una segunda regla que, si `actions.ngrok.rate_limit.limited`, responde **429** con cuerpo JSON en español y
  `Retry-After: 60`. Validada con la herramienta de validación de ngrok (válida); el primer intento falló por poner `expressions` dentro de la acción (va en la regla).
- Se aplica en ngrok antes de llegar a la API, así no consume la API local ni cambia ninguna ruta o el contrato. El tráfico local (`127.0.0.1:8000`) no pasa por el túnel y no se limita.
- La respuesta 429 **no** lleva `Access-Control-Allow-Origin` comodín (CORS exacto, principio VIII): la documentación (mismo origen) la lee sin él; el panel de Netlify la vería como backend inaccesible, algo que con 60 por minuto no ocurre.
- El agente se arranca con `--traffic-policy-file` (comprobado en la ayuda de `ngrok/ngrok:3.39.13-alpine`) y el fichero se monta de solo lectura.
- **Alternativas descartadas**: limitar dentro de la API con una biblioteca (dependencia nueva y vería siempre la dirección del agente de ngrok); limitar por cabecera `X-Forwarded-For` (falsificable).

## R5. Dónde viven `/docs` y la redirección de `/`

En la **API**, no en la política: se prueban con pytest sin túnel, funcionan igual en local y por el túnel y no dependen de una configuración externa. Son rutas de interfaz (`include_in_schema=False`): no aparecen en el
contrato. `/` responde con una redirección temporal a `/docs`; cualquier otra ruta inexistente sigue siendo un 404 explícito. `/redoc` sigue desactivada (no se pidió).

## R6. Contenido de la documentación

- Metadatos de OpenAPI en español: título, descripción general (qué es, procedencia USGS, «no es una predicción ni una evaluación de riesgo», solo lectura, límite de 60 peticiones por minuto, página intermedia de ngrok),
  etiquetas, `summary` y `description` por endpoint, ejemplos en los parámetros y ejemplos de respuesta para 200, 422, 503 y 500. Los **nombres, tipos, valores por defecto y rangos de los parámetros no cambian**.
- Una prueba de contrato compara rutas, métodos y nombres de parámetros con los de la 006 para garantizar que ningún cambio de metadatos altera el contrato.
- Solo `GET` en «Probar» (`supportedSubmitMethods: ["get"]`).

## R7. Qué no cambia

`/api/eventos`, `/api/estadisticas`, `/api/salud`, `/api/openapi.json` (misma ruta), CORS, el panel y sus pruebas, la base de datos y el resto de servicios. Las 79 pruebas de `tests/query_api` siguen en verde.

## R8. Orquestación

Sesión principal: `api/app/docs.py` y `main.py`, `compose.yaml` y la política del túnel, todo lo que toca Docker, ngrok y el navegador, evidencias y memoria. Sonnet (en segundo plano): `test_public_docs.py` y el texto de los
metadatos de OpenAPI a partir de un fichero. Haiku: el README de evidencia. Cada agente toca solo los ficheros de su tarea, sin commit.

## Corrección posterior a R4 (verificación T016)

La política de R4 se había validado solo con la herramienta de ngrok, que comprueba la sintaxis. Con la acción `rate-limit` en su modo por defecto, ngrok responde él mismo con un 429 vacío (`Retry-After` propio, sin cuerpo) y la regla `custom-response` nunca se ejecuta. Se añadió `enforce: false` a la acción: solo evalúa, y la regla `actions.ngrok.rate_limit.limited` devuelve el 429 en español. Evidencia: `docs/evidence/011/z9-rate-limit.md`.
