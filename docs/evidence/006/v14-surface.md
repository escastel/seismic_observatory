# V14 · Superficie de la API y retirada de lo heredado

**Fecha**: 2026-11-16 18:56 UTC · **Rama**: `006-query-api` · **Resultado**: SUPERADA

Rutas publicadas, métodos y alias heredados, contra la API real y con búsqueda en el repositorio.

| Comprobación | Esperado | Observado | |
|---|---|---|---|
| Rutas del contrato | /api/eventos, /api/estadisticas, /api/salud | ['/api/estadisticas', '/api/eventos', '/api/salud'] | ✓ |
| Solo GET documentado | get | {'/api/eventos': ['get'], '/api/salud': ['get'], '/api/estadisticas': ['get']} | ✓ |
| POST /api/eventos | 405 | 405 | ✓ |
| PUT /api/eventos | 405 | 405 | ✓ |
| DELETE /api/eventos | 405 | 405 | ✓ |
| GET /docs | 404 | 404 | ✓ |
| GET /redoc | 404 | 404 | ✓ |
| GET /api/health | 404 | 404 | ✓ |
| GET /api/estadisticas/paises | 404 | 404 | ✓ |
| GET /api/estadisticas/timeline | 404 | 404 | ✓ |
| GET /api/admin | 404 | 404 | ✓ |
| Alias retirados se ignoran | 200 FeatureCollection (sin filtrar por alias) | 200 FeatureCollection | ✓ |
| Puerto publicado solo en 127.0.0.1 | 127.0.0.1:8000->8000 | 127.0.0.1:8000 | ✓ |

## Uso de lo heredado en el repositorio (T032)

Búsqueda en `frontend/src/`, `resources/observatorio-sismico/frontend/src/`, `compose.yaml`, `README.md`,
`docs/`, `tests/` y los servicios (excluidas las specs 001 a 005 y evidencias antiguas):

| Heredado | Uso encontrado | Decisión |
|---|---|---|
| `format=geojson` | `frontend/src/app/app.component.ts:101` (lo envía) | Se acepta y se ignora: la respuesta ya es siempre `FeatureCollection` (comprobado arriba) |
| `limit` | `frontend/src/app/app.component.ts:101` | Se conserva: es el tamaño de página del contrato |
| `country` (nombre) | `frontend/src/app/app.component.ts:102` | Retirado; se ignora. **Traspaso a la spec 007**: usar `country_id` |
| `date_from`, `date_to`, `min_magnitude`, `max_magnitude` | ninguno | Retirados |
| `/api/estadisticas/paises`, `/api/estadisticas/timeline` | ninguno (el panel usa `/api/estadisticas`) | Retiradas (404 comprobado) |
| `/api/health` | ninguno (el healthcheck de Compose usa `/api/salud`) | Retirada |
| `format=json` y respuesta `{items,count,limit,offset}` | ninguno | Retiradas |
| propiedad `country` del `Feature` | `frontend/src/app/app.component.ts` (popup) | Retirada; el contrato define `country_name`. **Traspaso a la spec 007** |
| `/api/eventos?limit=1` | `tests/integration/load_test.py` | Sigue válido |

El frontend del paquete del profesor (`resources/observatorio-sismico/frontend/src/`) no usa ninguno de
los alias. No queda ningún alias conservado, por lo que no hay fecha de retirada.
