# 011 · La raíz redirige a `/docs` (T010: Z2)

Pruebas automáticas: `test_root_redirects_to_docs` y 404 explícitos pasan (14 verdes en `test_public_docs.py`; las 6 restantes son de metadatos, Fase 5).

| Petición | Esperado | Local | Dominio público |
|---|---|---|---|
| `GET /` | 307, `Location: /docs`, sin cuerpo | 307 `location: /docs`, `content-length: 0` | 307 `Location: /docs`, `Content-Length: 0` |
| `GET /` siguiendo redirecciones | termina en `/docs` con 200 | — | `https://modular-guidance-daybreak.ngrok-free.dev/docs` 200 |
| `GET /otra-cosa` | 404 | 404 | 404 |
| `GET /redoc` | 404 | 404 | 404 |
| `GET /admin`, `/metrics` | 404 | 404 | 404 |
| `POST /api/eventos` | 405 | 405 | 405 |

Todas las peticiones por el dominio público llevaron `ngrok-skip-browser-warning: true` para no recibir la página intermedia.
