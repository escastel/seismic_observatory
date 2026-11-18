# 011 · `/docs` en local (T007: Z1, Z3, Z5)

Navegador: Chrome (Puppeteer, headless) contra `http://127.0.0.1:8000/docs`, API reconstruida con `docker compose up --build -d api`.
Datos completos en [z1-local-report.json](z1-local-report.json); capturas enlazadas abajo.

| Comprobación | Esperado | Observado |
|---|---|---|
| Z1: la página carga con los tres endpoints | `/api/eventos`, `/api/salud`, `/api/estadisticas` | los tres presentes; título «Observatorio Sísmico · API»; aviso visible de `cdn.jsdelivr.net` ([captura](z1-local-1-overview.png)) |
| Z3: «Probar» `GET /api/salud` | JSON real | `{"status":"ok","database":"ok","replay_database":"ok",…}` ([captura](z1-local-2-salud.png)) |
| Z3: «Probar» `GET /api/eventos?min_mag=5` | FeatureCollection real | `count 9, total 9`, modo `live` ([captura](z1-local-3-eventos-minmag5.png)) |
| El `curl` generado lleva la cabecera de omisión | `ngrok-skip-browser-warning: true` | presente en los tres `curl` generados |
| Z5: parámetro inválido muestra el 422 con parámetro y motivo | `invalid_parameters` | `limit=0` → `{"param":"limit","message":"must be between 1 and 1000"}` ([captura](z1-local-4-eventos-422-limit0.png)) |
| Z5: `min_mag` no numérico | 422 con parámetro y motivo | el campo quedó con `5abc` (el script añadió texto al valor previo, no `abc` a secas); respuesta `{"param":"min_mag","message":"Input should be a valid number, unable to parse string as a number"}` ([captura](z1-local-5-eventos-minmag-abc.png)) |

Notas: la consola del navegador solo muestra un 404 (resolución de `/favicon.ico`, que da 404 en la API; no comprobado en la petición concreta del navegador) y los dos 422 provocados. Ninguna petición fallida de red.
Limitación: el valor exacto `min_mag=abc` no se probó solo; la prueba equivalente es `5abc`.
