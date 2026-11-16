# V13 · Validación 422 y acceso CORS

**Fecha**: 2026-11-16 18:56 UTC · **Rama**: `006-query-api` · **Resultado**: SUPERADA

Peticiones a la API real con parámetros inválidos y con preflights desde un origen permitido y otro no.

| Comprobación | Esperado | Observado | |
|---|---|---|---|
| /eventos?mode=x | 422 con param mode | 422 {'error': 'invalid_parameters', 'detail': [{'param': 'mode', 'message': "must be 'live' or 'replay', got 'x'"}]} | ✓ |
| /eventos?start=2025-01-01 | 422 con param start | 422 {'error': 'invalid_parameters', 'detail': [{'param': 'start', 'message': 'must be an ISO 8601 instant with a time zone, e.g. 2025-03-01T00:00:00Z'}]} | ✓ |
| /eventos?start=2025-02-01T00:00:00Z&end=2025-01-01T00:00:00Z | 422 con param start | 422 {'error': 'invalid_parameters', 'detail': [{'param': 'start', 'message': 'must be earlier than end (start is inclusive, end is exclusive)'}]} | ✓ |
| /eventos?min_mag=abc | 422 con param min_mag | 422 {'error': 'invalid_parameters', 'detail': [{'param': 'min_mag', 'message': 'Input should be a valid number, unable to parse string as a number'}]} | ✓ |
| /eventos?min_mag=nan | 422 con param min_mag | 422 {'error': 'invalid_parameters', 'detail': [{'param': 'min_mag', 'message': 'must be a finite number'}]} | ✓ |
| /eventos?limit=0 | 422 con param limit | 422 {'error': 'invalid_parameters', 'detail': [{'param': 'limit', 'message': 'must be between 1 and 1000'}]} | ✓ |
| /eventos?limit=100000 | 422 con param limit | 422 {'error': 'invalid_parameters', 'detail': [{'param': 'limit', 'message': 'must be between 1 and 1000'}]} | ✓ |
| /eventos?offset=-1 | 422 con param offset | 422 {'error': 'invalid_parameters', 'detail': [{'param': 'offset', 'message': 'Input should be greater than or equal to 0'}]} | ✓ |
| /eventos?country_id=%3Bdrop | 422 con param country_id | 422 {'error': 'invalid_parameters', 'detail': [{'param': 'country_id', 'message': 'must be 1 to 8 letters or digits, e.g. ESP'}]} | ✓ |
| Preflight desde https://evil.example (API en marcha) | sin access-control-allow-origin | 400 allow-origin=None | ✓ |
| Segunda instancia con CORS_ORIGINS del contrato | arranca | True | ✓ |
| Preflight desde https://observatorio-demo.netlify.app | origen concedido, GET y OPTIONS, cabecera de ngrok, sin credenciales | 200 allow-origin=https://observatorio-demo.netlify.app methods=GET, OPTIONS headers=Accept, Accept-Language, Content-Language, Content-Type, ngrok-skip-browser-warning credentials=None | ✓ |
| Preflight desde http://localhost:4200 | origen concedido, GET y OPTIONS, cabecera de ngrok, sin credenciales | 200 allow-origin=http://localhost:4200 methods=GET, OPTIONS headers=Accept, Accept-Language, Content-Language, Content-Type, ngrok-skip-browser-warning credentials=None | ✓ |
| Preflight desde otro origen | sin allow-origin | 400 allow-origin=None | ✓ |

## Notas

- El origen de Netlify real y la lista de `CORS_ORIGINS` del `.env` local no se leen ni se imprimen: la comprobación positiva se hace con una segunda instancia de la API (puerto 8001 solo en 127.0.0.1, contenedor temporal) configurada con orígenes de ejemplo exactos. Con el `.env` local, un origen que no esté en su lista recibe 400 sin `access-control-allow-origin`.

- Tras añadir `http://localhost:4200` al `CORS_ORIGINS` del `.env` local (sin leerlo ni imprimirlo) y recrear la API, el preflight desde ese origen contra la API en marcha devuelve 200 con `access-control-allow-origin: http://localhost:4200` y `GET, OPTIONS`; un origen no listado sigue recibiendo 400.
