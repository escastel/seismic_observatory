# 011 · `/docs` por el dominio público (T008: Z4)

Navegador: Chrome (Puppeteer) contra `https://modular-guidance-daybreak.ngrok-free.dev/docs`. Datos en [z4-public-report.json](z4-public-report.json).

| Comprobación | Esperado | Observado |
|---|---|---|
| Página intermedia de ngrok | aparece y se supera como una persona (botón «Visit Site») | apareció (`interstitialShown: true`) y se superó pulsando el botón |
| `/docs` carga tras la página intermedia | tres endpoints | `/api/eventos`, `/api/salud`, `/api/estadisticas` ([captura](z4-public-1-overview.png)) |
| «Probar» `GET /api/salud` | JSON real, no HTML de ngrok | `{"status":"ok","database":"ok","replay_database":"ok",…}` ([captura](z4-public-2-salud.png)) |
| «Probar» `GET /api/eventos?min_mag=5` | JSON real | FeatureCollection real ([captura](z4-public-3-eventos-minmag5.png)) |
| 422 desde «Probar» | JSON con parámetro y motivo | `limit=0` y `min_mag` inválido devuelven `invalid_parameters` con su motivo ([captura](z4-public-4-eventos-422-limit0.png)) |
| Errores de CORS / peticiones fallidas | ninguno | `failedRequests: []`; la consola solo recoge un 404 y los dos 422 provocados |

Conclusión: el `requestInterceptor` con `ngrok-skip-browser-warning: true` hace que «Probar» reciba JSON por el dominio público.
