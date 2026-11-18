# Modelo de datos

Esta feature **no toca la base de datos ni el modelo de la 002**. Las entidades de la spec son de interfaz y de configuración, no de almacenamiento.

## Documentación interactiva

| Campo | Descripción |
|---|---|
| Ruta | `GET /docs` (fuera del contrato OpenAPI) |
| Fuente | el contrato publicado en `/api/openapi.json` |
| Recursos externos | `swagger-ui-dist@5.17.14` desde `cdn.jsdelivr.net`, con SRI |
| Comportamiento de «Probar» | solo `GET`; añade `ngrok-skip-browser-warning: true` a cada petición |
| Cabecera de seguridad | `Content-Security-Policy` limitada a `'self'` y jsDelivr |

## Contrato publicado

Los tres endpoints existentes (`/api/eventos`, `/api/estadisticas`, `/api/salud`), sin rutas, métodos, parámetros, tipos ni valores por defecto nuevos. Lo que se añade son **metadatos**: descripción general, etiquetas,
`summary` y `description` por operación, ejemplos de parámetros y ejemplos de respuesta 200, 422, 503 y 500.

## Redirección de la raíz

`GET /` → redirección temporal a `/docs`; no aparece en el contrato. Cualquier otra ruta inexistente: 404 explícito.

## Límite de peticiones (configuración del túnel)

| Campo | Valor |
|---|---|
| Clave | dirección de origen del visitante |
| Capacidad y ventana | 60 peticiones por 60 s (ventana deslizante) |
| Respuesta al superarlo | 429, `Content-Type: application/json`, `Retry-After: 60`, cuerpo `{"error":"too_many_requests","message":"Demasiadas peticiones. …"}` en español |
| Ámbito | solo el tráfico que entra por el dominio público; el tráfico local no pasa por el túnel |
