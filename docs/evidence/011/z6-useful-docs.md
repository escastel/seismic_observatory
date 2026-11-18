# 011 · Documentación comprensible (T012: Z6)

Una «persona sin contexto» (un agente de IA sin contexto, sin acceso al repositorio) recibió solo `GET /api/openapi.json` y el HTML de `/docs`, guardados aparte, y debía obtener los eventos de magnitud ≥ 5 de las últimas 24 horas. Duración del agente: **≈ 7 s** (2 lecturas).

| Esperado | Observado |
|---|---|
| Identifica la petición correcta | `GET /api/eventos?min_mag=5`; sabe que sin `start` en `live` se toman las últimas 24 h y que `mode` es `live` por defecto |
| Sabe qué esperar | 200 con `FeatureCollection` y `metadata` (`total`, `count`, `truncated`, `next_offset`); pagina con `offset` si `truncated` |
| Conoce los errores | 422, 429 (60 peticiones por minuto, `Retry-After: 60`), 503 y 500 |

Dudas que anotó (mejoras posibles, no bloqueantes):
- No dice el host: solo rutas relativas (es esperable, `/docs` se sirve en el propio dominio).
- El esquema de la respuesta 200 está vacío y solo hay un ejemplo con `features` vacío: no describe las propiedades de cada evento.
- No aclara si `next_offset` solo aparece con `truncated: true` ni si `min_mag=5` incluye 5,0.
- Tiempos en milisegundos Unix en la respuesta e ISO 8601 en `start`/`end`.
- No hay `curl` de ejemplo (Swagger lo genera al pulsar «Probar»).

Capturas de la descripción general (nota de procedencia, límite de 60 por minuto y aviso de jsDelivr): [z6-docs-description.png](z6-docs-description.png). Ambos esquemas de color: ver [z11-z12-resources-a11y.md](z11-z12-resources-a11y.md) (Swagger UI no tiene tema oscuro).
