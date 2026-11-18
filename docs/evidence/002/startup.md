# Arranque, superficie, persistencia, reintentos y túnel (V1, V2, V8, V9, V10)

- Observado (UTC): 2026-11-15T00:26:50Z a 2026-11-15T00:35:12Z
- Rama y commit: 002-platform-data-model @ 41d68ee (más el cambio de imagen de ngrok descrito en V10)
- Equipo: MINGW64_NT-10.0-26200 3.5.4-cbe555e0.x86_64 x86_64
- Motor: Docker 29.1.3 (Docker Desktop (containerized)), Compose 2.40.3-desktop.1; recursos del motor: 12 CPU, 7.6 GiB

Antes de V1 se recreó el volumen con `docker compose down -v`, con confirmación expresa de la
persona autora (T041). Los diez arranques desde cero de V1 se miden aparte en
[cold-starts.md](cold-starts.md) (T055).

## Resumen

| Escenario | Esperado | Observado | Resultado |
|---|---|---|---|
| V1 | Cinco servicios `healthy` en menos de 3 min con las imágenes construidas; ningún `tunnel` | Cinco servicios `healthy` 21 s después de `down -v`; `tunnel` no arranca sin `--profile tunnel` | SUPERADA |
| V2 | Solo `api` publica puerto, en `127.0.0.1:8000`; 5432, 9092 y 8000 no responden desde otro dispositivo | Solo `api 127.0.0.1:8000->8000/tcp`; desde la IP de red local del propio equipo, 5432, 9092, 29092 y 8000 cerrados | SUPERADA en el equipo; la prueba desde otro dispositivo se descartó el 2026-11-17 a petición de la persona autora por no ser necesaria para el enunciado (§9 exige exponer solo la API, y lo garantiza la publicación de puertos de `compose.yaml`) |
| V8 | Mismo recuento tras reiniciar; el productor no republica; todo `publish_state` aparece en `message_log` | 193 eventos antes y después; «Published 0» tras reiniciar; 0 eventos publicados sin mensaje registrado | SUPERADA |
| V9 | Reintentos con espera creciente, recuperación sin reinicio manual, `/api/salud` degradado durante la caída | Esperas de 1, 2, 4, 8 y 16 s en el productor; recuperación sola; `degraded` durante la caída y `ok` después | SUPERADA |
| V10 | Con `NGROK_AUTHTOKEN` y `NGROK_DOMAIN`, la URL HTTPS responde en `/api/salud` | Con `ngrok/ngrok:3.18.4-alpine` el agente es rechazado (ERR_NGROK_121); con `3.39.13-alpine`, HTTPS responde 200 | SUPERADA tras cambiar la imagen |

## V1. Arranque desde cero

```text
$ docker compose down -v
 Volume seismic_observatory_postgres_data  Removed
$ docker compose up -d --wait --wait-timeout 300
 Container seismic_observatory-kafka-1  Healthy
 Container seismic_observatory-postgres-1  Healthy
 Container seismic_observatory-api-1  Healthy
 Container seismic_observatory-consumer-1  Healthy
 Container seismic_observatory-producer-1  Healthy
exit=0 tiempo=21s

$ docker compose ps --format 'table {{.Service}}\t{{.State}}\t{{.Status}}\t{{.Ports}}'
SERVICE    STATE     STATUS                    PORTS
api        running   Up 9 seconds (healthy)    127.0.0.1:8000->8000/tcp
consumer   running   Up 6 seconds (healthy)
kafka      running   Up 20 seconds (healthy)   9092/tcp
postgres   running   Up 20 seconds (healthy)   5432/tcp
producer   running   Up 6 seconds (healthy)
```

`9092/tcp` y `5432/tcp` son puertos que la imagen declara, no publicados en el equipo: no
llevan `->`.

Un evento real recorre el sistema sobre el modelo nuevo (punto de control del MVP):

```text
producer  Created Kafka topics earthquakes.live, earthquakes.catalog, earthquakes.replay with retention 168 h
producer  Fetched 193 events from https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson
producer  Published 193 earthquake versions to earthquakes.live
consumer  Processed topic=earthquakes.live partition=0 offset=0 ... offset=192 outcome=new

 published | messages | current | versions | quarantined | no_country | replay_rows
-----------+----------+---------+----------+-------------+------------+-------------
       193 |      193 |     193 |      193 |           0 |         38 |           0

$ curl -s http://127.0.0.1:8000/api/salud
{"status":"ok","last_ingestion":"2026-11-15T00:27:28.818667+00:00"}
$ curl -s "http://127.0.0.1:8000/api/eventos?limit=2"
{"items":[{"id":"ci41362279","updated":"2026-11-15T00:22:15.180000Z","time":"2026-11-15T00:18:53.980000Z",
 "mag":0.95,"magType":"ml","place":"10 km S of Idyllwild, CA", ... ,"country":"Estados Unidos",
 "source":"usgs_feed","country_id":"USA"}, ...],"count":193,"limit":2,"offset":0}
```

El consumidor, con un grupo nuevo, empezó en el offset 0 y procesó las 193 versiones que el
productor había publicado antes de que se uniera (R20). 38 eventos quedan sin país (mar).

## V2. Superficie expuesta

```text
$ docker compose ps --format '{{.Service}} {{.Ports}}'
api 127.0.0.1:8000->8000/tcp
consumer
kafka 9092/tcp
postgres 5432/tcp
producer

Sondeo TCP desde el propio equipo (bash /dev/tcp, 3 s de espera):
localhost:5432 cerrado     IP-LAN:5432 cerrado
localhost:9092 cerrado     IP-LAN:9092 cerrado
localhost:29092 cerrado    IP-LAN:29092 cerrado
localhost:8000 abierto     IP-LAN:8000 cerrado
```

La API solo responde en `127.0.0.1`. La comprobación desde otro dispositivo de la red no se hizo y se descartó el 2026-11-17 a petición de la persona autora
(no es necesaria para el enunciado): esta parte del escenario no se da por observada.

## V8. Persistencia tras reinicio

```text
antes   (current|published|messages|published_sin_mensaje): 193|193|193|0
$ docker compose down && docker compose up -d --wait
up exit=0 20s
después (current|published|messages|published_sin_mensaje): 193|193|193|0
producer  Fetched 193 events from .../all_day.geojson
producer  Published 0 earthquake versions to earthquakes.live
consumer  mensajes procesados tras reiniciar: 0 (offsets confirmados conservados en kafka_data)
```

## V9. Reintentos

Caída de PostgreSQL de 75 s (`docker compose stop postgres`, espera, `docker compose start
postgres`), de modo que coincida con un ciclo del productor:

```text
t+40s salud={"status":"degraded","last_ingestion":null}
producer  00:31:25 producer cycle failed (attempt 1): [Errno -5] No address associated with hostname; retrying in 1 s
producer  00:31:30 producer cycle failed (attempt 2): ...; retrying in 2 s
producer  00:31:37 producer cycle failed (attempt 3): ...; retrying in 4 s
producer  00:31:45 producer cycle failed (attempt 4): ...; retrying in 8 s
producer  00:31:57 producer cycle failed (attempt 5): ...; retrying in 16 s
producer  00:32:13 Published 0 earthquake versions to earthquakes.live
api       Health check could not query the database: [Errno -5] No address associated with hostname (x7)
tras volver: {"status":"ok","last_ingestion":"2026-11-15T00:27:28.818667+00:00"}

SERVICE    STATUS
api        Up 4 minutes (healthy)
consumer   Up 4 minutes (healthy)
kafka      Up 4 minutes (healthy)
postgres   Up 45 seconds (healthy)
producer   Up 4 minutes (healthy)
```

Ningún servicio se reinició a mano. Durante la caída no llegó ningún mensaje nuevo, así que el
consumidor no necesitó la base; su reintento del mismo mensaje sin confirmar offsets
posteriores lo prueba `tests/unit/test_consumer_loop.py`.

## V10. Túnel opcional

Se comprobó solo por nombre que `NGROK_AUTHTOKEN` y `NGROK_DOMAIN` tienen valor en `.env`. El
dominio se oculta en esta evidencia.

Con la imagen fijada en el plan (research.md R13):

```text
$ docker compose --profile tunnel up -d
tunnel-1  | ERROR:  authentication failed: Your ngrok-agent version "3.18.4" is too old.
            The minimum supported agent version for your account is "3.29.0".
tunnel-1  | ERROR:  ERR_NGROK_121
```

Cambio aplicado en `compose.yaml`: imagen `ngrok/ngrok:3.39.13-alpine` (publicada el
2026-10-23) y `--log stdout` para que el agente escriba en `docker compose logs`. La sintaxis
del dominio reservado es `--url` en las dos versiones (`ngrok http --help`).

```text
$ docker compose --profile tunnel up -d
tunnel-1  | lvl=info msg="started tunnel" obj=tunnels name=command_line addr=<url> url=<url>
$ curl -s -H "ngrok-skip-browser-warning: 1" "https://***/api/salud"
{"status":"ok","last_ingestion":"2026-11-15T00:27:28.818667+00:00"} http=200
$ docker compose --profile tunnel stop tunnel
```

Sin `--profile tunnel` el servicio `tunnel` no arranca y los cinco obligatorios siguen sanos
(V1); `docker compose config --quiet` valida el fichero con las variables de ngrok vacías.
