# 011 · Límite de 60 peticiones por minuto (T016: Z9)

Prueba: 300 `GET /api/salud` en 54 s por **una sola conexión HTTPS persistente** al dominio público, con `ngrok-skip-browser-warning: true` (script fuera del repo). Una sola IP de origen (la de este equipo).

## Primer intento: fallo encontrado

Con la política de la investigación R4 (sin `enforce: false`) la ráfaga dio 59 × 200 y 241 × 429, pero el 429 **no** era el nuestro: `Retry-After: 40`, sin `Content-Type` y **cuerpo vacío**. La acción `rate-limit` rechaza ella misma, con su 429 genérico, y la regla `custom-response` nunca llegaba a ejecutarse. La validación de la herramienta de ngrok solo comprobó la sintaxis, no este comportamiento.

Corrección: `enforce: false` en la acción `rate-limit` (la documenta como «evalúa pero no aplica»), de modo que la regla `too-many-requests` (`actions.ngrok.rate_limit.limited`) responde. Política revalidada («the policy is valid») y túnel recreado.

## Segundo intento (política corregida)

| Comprobación | Esperado | Observado |
|---|---|---|
| Primeras ≈ 60 peticiones | 200 | 53 × 200; la primera 429 fue la nº 54 |
| Resto | 429 | 247 × 429 (la ráfaga era de 300) |
| Cuerpo del 429 | `{"error":"too_many_requests","message":"Demasiadas peticiones. Espera un minuto antes de volver a probar."}` | idéntico |
| Cabeceras del 429 | `Content-Type: application/json`, `Retry-After: 60`, sin `Access-Control-Allow-Origin` | `Content-Type: application/json`, `Retry-After: 60`; sin `Access-Control-Allow-Origin` |
| Inspector de ngrok (14:40:50–14:42:10 UTC) | coincide | 303 peticiones: 53 × 200 y 250 × 429; una única IP (212.170.131.217) |
| Tras ≈ 1 minuto | vuelve a responder 200 | 200 (14:43:06 UTC) |
| API local durante/después | responde con normalidad | 200 en `http://127.0.0.1:8000/api/salud` |
| Otro origen distinto | no limitado | **no comprobado** (no había un segundo origen disponible) |

Observaciones:
- Se cortó en 53 y no en 60: ngrok documenta que la capacidad se aplica por servidor de entrada y la ventana es deslizante; el valor exacto no es determinista. Por tanto «≈ 60».
- El inspector cuenta 3 peticiones más que el script (303 frente a 300): 3 respuestas 429 adicionales de la misma IP en esa ventana, cuyo origen no he identificado.
- La primera ráfaga (59 × 200, 241 × 429 con el 429 genérico) también limitó la IP de este equipo durante un minuto.
