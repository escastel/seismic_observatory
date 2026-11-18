# Guía de validación (quickstart)

Escenarios que prueban la feature de principio a fin. Cada uno guarda esperado y observado en `docs/evidence/011/` (skill `verify-stack`). Una prueba no está superada hasta que hay evidencia.

## Requisitos

- Stack levantado (`docker compose up --build -d`) y el túnel con su perfil (`docker compose --profile tunnel up -d`); dominio `https://modular-guidance-daybreak.ngrok-free.dev`.
- Para el navegador: `frontend/public/config.json` apuntando a la API local solo durante las capturas (restaurar al terminar: `git diff` vacío), Chrome con Puppeteer instalado fuera del repositorio.
- Nunca leer ni imprimir `.env`; no ejecutar `docker compose config`.

## Escenarios

| Id | Escenario | Cómo | Esperado |
|---|---|---|---|
| Z1 | Documentación local | abrir `http://127.0.0.1:8000/docs` | 200, título «Observatorio Sísmico · API», los tres endpoints con descripción y la nota de procedencia en español |
| Z2 | Raíz | `curl -i http://127.0.0.1:8000/` y por el dominio público | redirección a `/docs`, sin 404; `/otra-cosa` sigue dando 404 |
| Z3 | Probar (local) | en `/docs`, ejecutar `GET /api/salud` y `GET /api/eventos?min_mag=5` | respuesta real en la página, sin errores de red ni de CORS |
| Z4 | Probar por el dominio público | lo mismo en `https://modular-guidance-daybreak.ngrok-free.dev/docs` tras la página intermedia | respuesta real (no la página intermedia), sin errores de CORS |
| Z5 | Error explícito | en `/docs`, `GET /api/eventos?min_mag=abc` | 422 con el parámetro y el motivo visibles |
| Z6 | Documentación útil | una persona sin contexto obtiene los eventos de magnitud ≥ 5 de las últimas 24 horas solo con `/docs` | menos de 2 minutos |
| Z7 | Contrato intacto | `pytest tests/query_api` (una sola vez) y la prueba de contrato nueva | las 79 pruebas anteriores y las nuevas en verde; rutas, métodos y parámetros iguales a la 006 |
| Z8 | Solo lectura | probar `POST`, `PUT`, `DELETE`, `/redoc`, `/admin`, `/metrics` por el dominio | 404 o 405; ninguna operación de escritura en el contrato |
| Z9 | Límite de peticiones | ráfaga de 300 peticiones en un minuto desde un origen por el dominio; en paralelo, otro origen o la red del móvil | las que pasan de 60 reciben 429 en español con `Retry-After`; el otro origen y el panel responden con normalidad; el inspector de ngrok lo confirma |
| Z10 | Panel intacto | abrir el panel de Netlify, filtrar por Albania, cerrar y reabrir el túnel | mismos resultados que en la 010, sin errores de CORS |
| Z11 | Recursos exactos | inspeccionar `/docs` | `swagger-ui-dist@5.17.14` con `integrity`; los únicos dominios externos del navegador son `cdn.jsdelivr.net` (y los ya conocidos del panel, no de `/docs`) |
| Z12 | Accesibilidad básica | axe-core sobre `/docs` | sin violaciones atribuibles a la página propia (la interfaz de Swagger se evalúa y las excepciones se documentan) |
| Z13 | Documentación declarada | leer `docs/report.md` | recoge la reversión de R7, el límite, la declaración de recursos externos y la página intermedia de ngrok |
