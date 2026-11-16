# Evidencias de la spec 003: ingesta desde USGS

Resultados de los escenarios de [quickstart.md](../../../specs/003-usgs-ingestion/quickstart.md),
observados el 2026-11-15 entre las 11:31Z y las 19:05Z en Windows 11 Pro for Workstations con
Docker Desktop 29.1.3 (motor con 12 CPU y 7,6 GiB), contra los servicios reales de USGS salvo
donde se indica la fuente simulada. Ningún escenario se marca como superado sin haberlo
ejecutado; cada fichero enlazado incluye la orden, la cabecera de equipo y commit, y la salida.

| Escenario | Esperado | Observado | Resultado | Evidencia |
|---|---|---|---|---|
| V1 · Una hora de feed | 60 ± 1 consultas registradas, 0 descuadradas, originales = contenidos distintos, última ingesta < 2 min | 60 consultas (57 `ok`, 3 `not_modified`) entre 17:56Z y 18:56Z, 0 descuadradas, 17 originales para 17 contenidos, separación de 60 s, última ingesta hace 10 s. Un primer intento (11:34Z–12:34Z) se descartó porque el equipo se detuvo a las 12:00Z | SUPERADA | [feed.md](feed.md) |
| V2 · Exclusiones y no identificables | Voladura guardada como exclusión una vez; elemento sin `id` contado y descrito; 3 recibidos = 1 + 2 | Igual, en `tests/db/test_feed_cycle.py` contra la base real. En USGS real no apareció ningún elemento de otro tipo durante la observación | SUPERADA (prueba automática) | [tests.txt](tests.txt) |
| V3 · Fallos de la fuente | Cada fallo registrado con resultado e intentos; espera ≥ `Retry-After`; nada publicado ni borrado; `last_ingestion` quieta; productor `healthy`; recuperación sola | 503, 429 (`Retry-After: 5`, esperó 5 s), tiempo agotado, no JSON y estructura no válida: 4 extracciones cada uno, 0 publicadas, `last_ingestion` sin cambios, `healthy` siempre; vuelta a USGS con `ok` | SUPERADA | [source-failures.md](source-failures.md) |
| V4 · Carga de 2025 | Diferencia 0 con USGS; en `core` como `usgs_catalog`; nada en `replay`; huellas correctas; fuera de Git; < 15 min | 18.302 = 18.302 declarados; 18.302 en `core.event_current`; 0 en `replay`; 12 ficheros con huella correcta; `git status data/` vacío; ~1,5 min de orden | SUPERADA | [catalog-load.md](catalog-load.md) |
| V5 · Repetir y reanudar | Reanuda sin repetir; repetir no cambia nada | Cortada tras 5 meses y reanudada: 5 reutilizados, 7 descargados; repetición: 0 descargas, 0 publicados, recuentos iguales | SUPERADA | [catalog-load.md](catalog-load.md) |
| V6 · Subdivisión | Meses por encima de 20.000 divididos; nada descargado | Ningún mes real supera el máximo (el mayor con todas las magnitudes: 11.740); la división se comprueba con pruebas automáticas y el HTTP 400 real está en la investigación | SUPERADA con salvedad | [catalog-load.md](catalog-load.md) |
| V7 · Ampliación con 2026 | Diferencia 0; 2025 sin cambios; sin duplicados | 14.225 = 14.225 declarados; 2025 sigue en 18.302; 0 duplicados; 18 ya traídos por el feed conservan su versión | SUPERADA | [catalog-load-2026.md](catalog-load-2026.md) |
| V8 · Hueco tras una parada | Aviso con la orden en < 1 min; feed sigue; recuperación sin duplicados; `--gaps` lo da por recuperado | Parada simulada de 36 h (fechas desplazadas y restauradas exactamente); aviso a los 2 s; 128 = 128 declarados, 128 distintos en `core`; «recuperado» | SUPERADA (parada simulada) | [gap-recovery.md](gap-recovery.md) |
| V9 · Purga de originales | Purga al arrancar y cada 24 h con constancia en el log; nada más se borra; 0 cuerpos > 8 días | 3 pruebas en verde; «Purged 0 raw payload(s)» en cada arranque; 0 cuerpos > 8 días; 17 kB por cuerpo | SUPERADA; la eliminación real se observará desde el 2026-11-22 | [retention.md](retention.md) |
| V10 · Perfil de la fuente | Cada campo usado con tipo, ausencias y rango; frecuencia, errores y latencias | 37 respuestas del feed y 24 ficheros del catálogo analizados; los 11 campos usados con tipo, unidad y ausencias; latencias y retrasos medidos | SUPERADA | [source-profile.md](source-profile.md) |
| V11 · Mensaje publicado | Clave = id; `source`, `ingested_at`, `mode`, `extraction_id`, original | Mensaje real del offset 291: todos los campos; el consumidor lo registró | SUPERADA | [feed.md](feed.md) |
| V12 · Nada fuera de alcance | Pruebas de la 002 en verde; sin cambios en `db/sql`, consumidor, API ni panel | 303 pruebas superadas; `git diff 002-platform-data-model` vacío en esas rutas | SUPERADA | [tests.txt](tests.txt) |

## Pendiente

- **T050, permisos en Linux.** Comprobar en el equipo Linux que la carga escribe en `./data` con
  el usuario propio:

  ```bash
  LOADER_UID=$(id -u) LOADER_GID=$(id -g) docker compose run --rm catalog-loader --dry-run
  LOADER_UID=$(id -u) LOADER_GID=$(id -g) docker compose run --rm catalog-loader \
    --start 2025-01-01 --end 2025-01-02
  ls -ln data/usgs/catalog | tail -3      # propietario: el uid propio, no 0
  ```

  No se ha podido hacer en esta sesión (solo había acceso al equipo Windows). Hasta entonces la
  tarea queda sin marcar.

## Revisión constitucional (v2.1.0, T052)

| Principio | Estado al cerrar la 003 |
|---|---|
| I. Arquitectura reproducible | Cumple: `docker compose up --build -d` sigue arrancando cinco servicios; `catalog-loader` y `usgs-stub` solo existen bajo los perfiles `tools` y `test`; sin puertos ni dependencias nuevas; el productor funciona con el panel cerrado y consulta USGS cada 60 s |
| II. Al menos una vez, idempotente | Cumple: clave `event_id`; la versión se marca solo tras la confirmación de Kafka; feed y catálogo comparten `publish_state`; repetir la carga no publica nada (V5) |
| III. Calidad | Cumple en la ingesta: los tipos distintos de terremoto se conservan con motivo y extracción; los elementos no identificables se cuentan y se describen. Sigue abierta la desviación heredada del consumidor con la magnitud nula (spec 004); en esta sesión no afectó a ningún evento |
| V. Original y procedencia | **Cumple; cierra la desviación de la spec 002.** Original antes de transformar, una copia por contenido, retención de 7 días aplicada, toda consulta registrada (incluidos los recuentos y los fallos), subdivisión sin truncar, deduplicación, nada se borra, descargas fuera de Git con procedimiento de regeneración y huella verificable |
| VI. Aislamiento de la reproducción | Cumple: el histórico y los huecos van a `core` por `earthquakes.catalog`; 0 filas en `replay` tras las cargas |
| VII. Analítica desde el estado actual | Cumple: no hay contadores; la memoria indica qué periodos tienen todas las magnitudes y cuáles solo M ≥ 4, para comparar con el mismo filtro |
| VIII. Contrato de la API | Desviación conocida: la ingesta ya deja disponible `last_ingestion` como pide el contrato, pero la API aún no lo devuelve así (spec 006) |
| IX. Evidencia ejecutada | Cumple: esta tabla, con salida guardada de cada escenario, fallos probados con fuente simulada y mediciones reales de la fuente |
| Idioma y repositorio público | Cumple: código e identificadores en inglés, documentación en español; agente de usuario sin datos personales; `git status` no muestra `data/`, `.env` ni credenciales; ninguna evidencia contiene secretos de `.env` (`scan-evidence.sh`) |

Siguen abiertas las desviaciones de los principios III (spec 004) y VIII (spec 006). Mientras
existan, la rama no se fusiona en `main`.
