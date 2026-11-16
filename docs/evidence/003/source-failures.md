# Fallos de la fuente (US3: V3)

- Observado (UTC): 2026-11-15T18:57:41Z a 2026-11-15T19:01:25Z
- Rama y commit: 003-usgs-ingestion @ 0113c0f
- Equipo: MINGW64_NT-10.0-26200 3.5.4-cbe555e0.x86_64 x86_64
- Motor: Docker 29.1.3 (Docker Desktop (containerized)), Compose 2.40.3-desktop.1; recursos del motor: 12 CPU, 7,6 GiB

| | V3 |
|---|---|
| Esperado | Para saturación con `Retry-After`, error de servidor, tiempo agotado, cuerpo ilegible y estructura no válida: una extracción por consulta con su resultado, intentos y detalle; espera no inferior a la indicada; nada publicado ni borrado; `last_ingestion` sin avanzar; el productor sigue `healthy`; al volver a la fuente real, el ciclo siguiente es correcto |
| Observado | Los cinco casos registrados 4 veces cada uno con el resultado esperado; el 429 esperó los 5 s de `Retry-After`; los cuerpos ilegibles se guardaron; 0 versiones publicadas; `last_ingestion` quieta en 18:56:50Z; `healthy` en todos los casos; primera consulta real tras restaurar: `ok` |
| Resultado | SUPERADA |

Además, `tests/db/test_feed_failures.py` y `tests/unit/test_usgs_client.py` cubren los mismos
casos contra la base real con la fuente simulada en proceso (en [tests.txt](tests.txt)).

## Procedimiento

```bash
docker compose -f compose.yaml -f compose.dev.yaml --profile test up -d usgs-stub
docker compose stop producer
# Para cada ruta: un productor temporal con ciclos de 10 s, 2 intentos y 3 s de tiempo máximo,
# observado 40 s
docker compose -f compose.yaml -f compose.dev.yaml run -d --name producer-v3-<ruta> \
  -e USGS_FEED_URL=http://usgs-stub:8080/feed/<ruta> -e PRODUCER_INTERVAL_SECONDS=10 \
  -e USGS_MAX_ATTEMPTS=2 -e USGS_TIMEOUT_SECONDS=3 producer
docker inspect --format '{{.State.Health.Status}}' producer-v3-<ruta>
docker rm -f producer-v3-<ruta>
# Al terminar
docker compose start producer
docker compose -f compose.yaml -f compose.dev.yaml --profile test rm -sf usgs-stub
```

La fuente simulada es `tests/support/usgs_stub.py` (rutas `/feed/fail-503`, `/feed/fail-429`
con `Retry-After: 5`, `/feed/timeout` que tarda 600 s, `/feed/not-json` y
`/feed/bad-structure`). Solo existe dentro de la red de Compose.

## Productor frente a cada fallo

```text
=== fail-503 · salud: healthy
18:57:44 Feed request 193: outcome=http_error status=503 attempts=2 … published=0
18:57:54 Feed request 194: outcome=http_error status=503 attempts=2 … published=0
=== fail-429 · salud: healthy
18:58:30 Feed request 197: outcome=http_error status=429 attempts=2 … published=0
18:58:40 Feed request 198: outcome=http_error status=429 attempts=2 … published=0
=== timeout · salud: healthy
18:59:14 Feed request 201: outcome=timeout status=None attempts=2 … published=0
18:59:24 Feed request 202: outcome=timeout status=None attempts=2 … published=0
=== not-json · salud: healthy
18:59:49 Feed request 205: outcome=invalid_json status=200 attempts=1 … published=0
=== bad-structure · salud: healthy
19:00:31 Feed request 209: outcome=invalid_structure status=200 attempts=1 … published=0
```

Las consultas se suceden cada 10 s también cuando fallan: el ciclo registra el fallo, actualiza
el latido y espera al siguiente intervalo.

## Lo registrado en `core.extraction`

```text
     ruta      |      outcome      | http | intentos | duration_ms | recuentos | original | detalle
---------------+-------------------+------+----------+-------------+-----------+----------+-----------------------------------------------
 fail-503      | http_error        |  503 |        2 |        1009 | nulos     | no       | HTTP 503: Service Unavailable
 fail-429      | http_error        |  429 |        2 |        5008 | nulos     | no       | HTTP 429: Too Many Requests (Retry-After 5 s)
 timeout       | timeout           |      |        2 |        7012 | nulos     | no       | timeout after 3 s: HTTPConnectionPool(host='usgs-stub', …
 not-json      | invalid_json      |  200 |        1 |           6 | nulos     | sí       | response is not JSON: Expecting value: line 1 column 1 (char 0)
 bad-structure | invalid_structure |  200 |        1 |           6 | nulos     | sí       | expected type FeatureCollection, got 'Feature'

     ruta      | consultas | ms_min | ms_max
---------------+-----------+--------+--------
 fail-503      |         4 |   1005 |   1009     (1 s de espera entre los 2 intentos)
 fail-429      |         4 |   5004 |   5008     (5 s: la espera de Retry-After, mayor que el 1 s del retroceso)
 timeout       |         4 |   7007 |   7012     (3 s + 1 s + 3 s)
 not-json      |         4 |      2 |      6     (no se reintenta)
 bad-structure |         4 |      2 |      6     (no se reintenta)

last_ingestion: 2026-11-15 18:56:50Z   (última consulta correcta, a la fuente real, antes de los fallos)
versiones publicadas durante los fallos: 0
```

## Vuelta a la fuente real

```text
$ docker compose start producer
producer   Up 20 seconds (healthy)
19:01:23 Purged 0 raw payload(s) not seen for more than 7 days
19:01:25 Feed request 213: outcome=ok status=200 attempts=1 received=185 earthquakes=185 excluded=0 published=0
```

Las 20 extracciones de esta prueba quedan en `core.extraction` como registro de lo ocurrido; su
`request_url` (`http://usgs-stub:8080/…`) las distingue de las consultas reales.
