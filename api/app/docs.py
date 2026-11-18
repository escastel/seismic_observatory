"""Interactive API documentation page (Swagger UI) served at /docs.

Swagger UI assets come from jsDelivr with an exact version and Subresource Integrity, never
through the ngrok tunnel (free plan outbound cap). The page adds the ngrok interstitial-skip
header to every "Try it out" request so the browser receives JSON, not the ngrok HTML page.
"""

from __future__ import annotations

import json

SWAGGER_UI_VERSION = "5.17.14"
CDN_BASE = f"https://cdn.jsdelivr.net/npm/swagger-ui-dist@{SWAGGER_UI_VERSION}"
BUNDLE_URL = f"{CDN_BASE}/swagger-ui-bundle.js"
BUNDLE_INTEGRITY = "sha384-wmyclcVGX/WhUkdkATwhaK1X1JtiNrr2EoYJ+diV3vj4v6OC5yCeSu+yW13SYJep"
CSS_URL = f"{CDN_BASE}/swagger-ui.css"
CSS_INTEGRITY = "sha384-wxLW6kwyHktdDGr6Pv1zgm/VGJh99lfUbzSn6HNHBENZlCN7W602k9VkGdxuFvPn"

CONTENT_SECURITY_POLICY = (
    "default-src 'none'; "
    "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "img-src 'self' data: https://cdn.jsdelivr.net; "
    "connect-src 'self'"
)

_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Observatorio Sísmico · API</title>
<link rel="stylesheet" href="__CSS_URL__" integrity="__CSS_INTEGRITY__" crossorigin="anonymous">
<style>
  body { margin: 0; }
  .external-notice { margin: 0; padding: 8px 16px; background: #f4f4f4; color: #333;
    font: 14px/1.4 system-ui, sans-serif; border-bottom: 1px solid #ccc; }
</style>
</head>
<body>
<p class="external-notice">Esta página carga la interfaz de documentación desde
<strong>cdn.jsdelivr.net</strong>, que ve tu dirección IP y la página de origen (<em>Referer</em>).</p>
<main id="swagger-ui"></main>
<script src="__BUNDLE_URL__" integrity="__BUNDLE_INTEGRITY__" crossorigin="anonymous"></script>
<script>
  window.ui = SwaggerUIBundle({
    url: __OPENAPI_URL__,
    dom_id: "#swagger-ui",
    deepLinking: true,
    docExpansion: "list",
    supportedSubmitMethods: ["get"],
    requestInterceptor: function (request) {
      request.headers["ngrok-skip-browser-warning"] = "true";
      return request;
    }
  });
</script>
</body>
</html>
"""


def docs_page(openapi_url: str) -> str:
    """Return the /docs HTML for the given (relative) OpenAPI document URL."""
    return (
        _TEMPLATE.replace("__CSS_URL__", CSS_URL)
        .replace("__CSS_INTEGRITY__", CSS_INTEGRITY)
        .replace("__BUNDLE_URL__", BUNDLE_URL)
        .replace("__BUNDLE_INTEGRITY__", BUNDLE_INTEGRITY)
        .replace("__OPENAPI_URL__", json.dumps(openapi_url))
    )
