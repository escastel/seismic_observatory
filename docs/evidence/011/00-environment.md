# 011 · Estado «antes» (T001)

Fecha: 2026-11-18. Rama `011-public-api-docs`; `.specify/feature.json` apunta a `specs/011-public-api-docs`.

| Comprobación | Esperado | Observado |
|---|---|---|
| `GET http://127.0.0.1:8000/docs` | 404 | 404 |
| `GET http://127.0.0.1:8000/` | 404 | 404 |
| `GET http://127.0.0.1:8000/api/openapi.json` | 200 | 200 |
| `GET https://modular-guidance-daybreak.ngrok-free.dev/docs` (con `ngrok-skip-browser-warning`) | 404 | 404 |
| `GET …/` por el dominio público | 404 | 404 |
| `GET …/api/openapi.json` por el dominio público | 200 | 200 |
| `pytest tests/query_api` (sin el fichero nuevo de la 011) | 79 en verde | 79 passed in 29,95 s |

## Límites de ngrok (plan Free)

- Salida de datos del mes: 215 846 932 de 1 000 000 000 bytes (límite `OutgoingTrafficPerMonth`).
- Conexiones a endpoints por minuto (toda la cuenta): 100 (`ConnectionsToEndpointsPerMinute`); conexiones simultáneas: 100, en uso 2.
- Peticiones HTTP del periodo: 6848 de 20 000 incluidas.
- Reglas por política: 15; acciones por regla: 20; sesiones de agente: 3 (1 en uso).
- Ningún límite bloqueado ni cerca del tope.
