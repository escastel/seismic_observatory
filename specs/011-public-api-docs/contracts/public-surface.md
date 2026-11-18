# Contrato de la superficie pública

El contrato de los endpoints de datos es el de [`specs/006-query-api/contracts/api.md`](../../006-query-api/contracts/api.md) y **no cambia**. Este documento fija solo lo que se añade o se precisa en el dominio público.

## 1. Rutas accesibles desde fuera

| Ruta | Método | Respuesta | En el contrato OpenAPI |
|---|---|---|---|
| `/` | GET | redirección temporal a `/docs` | no |
| `/docs` | GET | HTML de la documentación interactiva (200) | no |
| `/api/openapi.json` | GET | contrato legible por máquinas (200) | — |
| `/api/eventos`, `/api/estadisticas`, `/api/salud` | GET | como en la 006 | sí |
| cualquier otra ruta | cualquiera | 404 explícito (405 si es una ruta conocida con método no admitido) | — |

No se publica ninguna ruta de escritura, de administración ni de métricas internas. `/redoc` sigue sin existir. Kafka y PostgreSQL no se publican nunca.

## 2. La página `/docs`

- Español en todos los textos propios. Título «Observatorio Sísmico · API».
- Descripción general visible (procedencia y límites): datos de USGS procesados por el proyecto, descriptivos, **no una predicción ni una evaluación de riesgo**; solo lectura; límite de 60 peticiones por minuto por visitante;
  la primera visita desde un navegador a un dominio gratuito de ngrok muestra una página intermedia; el navegador se conecta a `cdn.jsdelivr.net`, que ve la dirección IP y el `Referer`.
- Cada operación: `summary`, `description`, parámetros con descripción, valor por defecto, rango y ejemplo, y respuestas 200, 422, 503 y 500 con ejemplo.
- «Probar»: solo `GET`; cada petición lleva `ngrok-skip-browser-warning: true`; misma procedencia, sin CORS.
- Recursos: `swagger-ui-dist@5.17.14` (JavaScript y CSS) desde jsDelivr con `integrity` y `crossorigin="anonymous"`.
- Cabecera `Content-Security-Policy` con `script-src` y `style-src` limitados a `'self'`, `https://cdn.jsdelivr.net` y el arranque de la página.

## 3. Límite de peticiones (túnel)

- 60 peticiones por 60 s por dirección de origen, en `tunnel/traffic-policy.yml`.
- Al superarlo: `429`, `Content-Type: application/json`, `Retry-After: 60` y
  `{"error":"too_many_requests","message":"Demasiadas peticiones. Espera un minuto antes de volver a probar."}`. Sin `Access-Control-Allow-Origin` comodín.
- No altera rutas, parámetros ni encabezados CORS de los endpoints.

## 4. Invariantes (no negociables)

1. Los nombres de ruta, métodos, parámetros, tipos y valores por defecto de los tres endpoints son idénticos a los de la 006 (prueba de contrato).
2. CORS no cambia: orígenes exactos de Netlify y desarrollo, métodos `GET` y `OPTIONS`, cabecera `ngrok-skip-browser-warning`.
3. Ningún secreto en Git; el authtoken sigue en `.env`.
4. ngrok no se ejecuta dentro del proceso de la API.
