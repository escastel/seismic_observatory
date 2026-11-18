# 011 · No regresión y superficie pública (T018: Z7 y Z8)

## Z7 · Pruebas

| Comprobación | Esperado | Observado |
|---|---|---|
| `pytest tests/query_api` completa, una sola ejecución | 79 anteriores + 20 nuevas, todas en verde | **99 passed** en 38,04 s |
| `git diff origin/main` de `frontend/`, `consumer/`, `producer/`, `db/` y `common/` | vacío | 0 ficheros cambiados (tras `git fetch`) |
| Contrato de datos | rutas, métodos y parámetros iguales | `test_contract_paths_and_methods_unchanged` y `test_contract_parameter_names_unchanged` en verde; los tres endpoints y sus valores por defecto no se tocaron (solo se añadieron `description`, `examples`, `summary` y `responses`) |

## Z8 · Superficie pública por `https://modular-guidance-daybreak.ngrok-free.dev`

| Petición | Esperado | Observado |
|---|---|---|
| `POST`, `PUT`, `PATCH`, `DELETE /api/eventos` | 405 | 405 en los cuatro |
| `GET /redoc`, `/admin`, `/metrics`, `/docs/oauth2-redirect`, `/api/docs`, `/openapi.json` | 404 | 404 en todas |
| `GET /api/openapi.json` | solo tres rutas, solo `get` | `/api/eventos`, `/api/salud` y `/api/estadisticas`, solo `get` |
| `OPTIONS /api/eventos` con `Origin` de Netlify | CORS permitido | 200 con `Access-Control-Allow-Origin: https://seismicobservatoryecr.netlify.app` |

Todas las peticiones llevaron `ngrok-skip-browser-warning: true`.
