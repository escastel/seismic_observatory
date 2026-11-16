# V12 · Base caída y recuperación

**Fecha**: 2026-11-16 18:56 UTC · **Rama**: `006-query-api` · **Resultado**: SUPERADA

Se detiene el contenedor de PostgreSQL con `docker compose stop postgres`, se consulta la API y se vuelve a levantar. El productor y el consumidor dependen de la base: se reanudan al volver a levantarla.

| Comprobación | Esperado | Observado | |
|---|---|---|---|
| Antes: salud | ok | {'status': 'ok', 'database': 'ok', 'replay_database': 'ok', 'generated': 1794862759514, 'last_ingestion': 1794862743793} | ✓ |
| Base caída: /eventos | 503 JSON database_unavailable, nunca features vacías con 200 | 503 {'error': 'database_unavailable', 'detail': 'The database could not answer the query'} | ✓ |
| Base caída: /estadisticas | 503 JSON database_unavailable, nunca features vacías con 200 | 503 {'error': 'database_unavailable', 'detail': 'The database could not answer the query'} | ✓ |
| Base caída: /eventos?mode=replay | 503 JSON database_unavailable, nunca features vacías con 200 | 503 {'error': 'database_unavailable', 'detail': 'The database could not answer the query'} | ✓ |
| Base caída: salud | 200 degraded, last_ingestion null, sin credenciales | {'status': 'degraded', 'database': 'unavailable', 'replay_database': 'unavailable', 'generated': 1794862779454, 'last_ingestion': None} | ✓ |
| Recuperación sin reiniciar la API | salud vuelve a ok | {'status': 'ok', 'database': 'ok', 'replay_database': 'ok', 'generated': 1794862782830, 'last_ingestion': 1794862743793} | ✓ |
| Recuperación: eventos | 200 con datos | 200 total=196 | ✓ |
