# 011 · Pruebas primero (T004)

Orden: `docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m pytest tests/query_api/test_public_docs.py -q`

Esperado: fallan las de `/docs`, raíz y metadatos; pasan las de contrato y CORS.
Observado: **10 failed, 10 passed** (6,22 s) antes de implementar.

Fallan (correcto):
- `test_docs_page_is_html`, `test_docs_page_pins_swagger_ui_with_integrity`, `test_docs_page_sends_content_security_policy`
- `test_root_redirects_to_docs`
- `test_general_description_has_provenance_and_limit`, `test_every_operation_has_summary_and_description`, `test_every_parameter_has_description`
- `test_documented_responses` (eventos, estadísticas y salud)

Pasan (contrato y CORS intactos): rutas, métodos y parámetros, 404 en `/otra-cosa` y `/redoc`, sin operaciones de escritura, `POST /api/eventos` → 405, CORS.

Aviso: tres pruebas pasan antes de implementar sin que código nuevo las cumpla
(`test_docs_page_has_no_floating_version`, `test_docs_and_root_are_not_in_openapi`,
`test_unknown_routes_are_explicit_404[/redoc]`). Son guardas contra regresión, no un rojo previo.
