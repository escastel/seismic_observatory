# Retención de originales (US5: V9)

- Observado (UTC): 2026-11-15T17:55Z a 2026-11-15T18:05Z
- Rama y commit: 003-usgs-ingestion @ 5638abc más la documentación de la 003 (sin commit al observar)
- Equipo: MINGW64_NT-10.0-26200 3.5.4-cbe555e0.x86_64 x86_64
- Motor: Docker 29.1.3 (Docker Desktop (containerized)), Compose 2.40.3-desktop.1; recursos del motor: 12 CPU, 7,6 GiB

| | V9 |
|---|---|
| Esperado | Se eliminan los cuerpos no observados desde hace más de la retención; se conservan los recientes, las referencias a ficheros y todas las extracciones; el productor anota cuántos eliminó; con el sistema real, 0 cuerpos sin observar desde hace más de 8 días |
| Observado | Las 3 pruebas pasan (1 cuerpo antiguo eliminado de 3, las extracciones intactas, una caída de la base no detiene el feed, purga al arrancar y cada 24 h). El productor anotó la purga del arranque: 0 eliminados, porque el sistema lleva menos de 7 días guardando originales. 0 cuerpos con más de 8 días |
| Resultado | SUPERADA. La eliminación real de cuerpos caducados solo puede observarse a partir del 2026-11-22, cuando el primer original cumpla 7 días |

## Pruebas

```text
$ docker compose -f compose.yaml -f compose.dev.yaml run --rm tests pytest tests/db/test_purge_cycle.py -v
tests/db/test_purge_cycle.py::test_purge_removes_only_old_feed_bodies PASSED
tests/db/test_purge_cycle.py::test_purge_failure_is_logged_and_does_not_raise PASSED
tests/db/test_purge_cycle.py::test_purge_runs_at_start_and_every_24_hours PASSED
3 passed in 1.90s
```

## Constancia de la purga (FR-033)

```text
producer-1 | 2026-11-15T17:55:48.913Z INFO service=producer __main__ Purged 0 raw payload(s) not seen for more than 7 days
```

## Estado y tamaño de los originales

```text
cuerpos_sin_observar_8_dias: 0

 encoding | filas | sin_comprimir | comprimido_en_la_base
----------+-------+---------------+-----------------------
 file     |    23 | 22 MB         | 0 bytes          (12 ficheros de 2025 y 11 de 2026, en data/)
 gzip     |    18 | 2408 kB       | 305 kB           (respuestas distintas del feed)

tamaño total de core.raw_payload: 416 kB · core.extraction: 112 kB
tamaño medio de un cuerpo del feed comprimido: 17,0 kB
```

Contraste con la estimación del plan (17 kB por contenido distinto, como mucho uno por minuto):
el tamaño medio medido coincide. En el periodo observado el feed no cambió en cada consulta (18
contenidos distintos en las consultas hechas hasta ahora; ver
[source-profile.md](source-profile.md)), así que el máximo de 175 MB en 7 días es una cota
superior holgada.
