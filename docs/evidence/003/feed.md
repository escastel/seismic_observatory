# Feed en vivo con procedencia (US1: V1, V8 de la spec 002, V11)

- Observado (UTC): 2026-11-15T11:31Z a 2026-11-15T11:35Z (V1: ver su apartado)
- Rama y commit: 003-usgs-ingestion @ 1614271 más el ciclo nuevo del productor (sin commit al observar)
- Equipo: MINGW64_NT-10.0-26200 3.5.4-cbe555e0.x86_64 x86_64
- Motor: Docker 29.1.3 (Docker Desktop (containerized)), Compose 2.40.3-desktop.1; recursos del motor: 12 CPU, 7,6 GiB

## Resumen

| Escenario | Esperado | Observado | Resultado |
|---|---|---|---|
| Arranque con el productor nuevo | Cinco servicios sanos; cada consulta registrada | Cinco `healthy` en 17 s; «Feed request 1/2: outcome=ok … received=192 earthquakes=192 excluded=0» | SUPERADA |
| V8 de la spec 002 (reinicio) | Mismo recuento; no se republica nada | 273 eventos, 274 publicados y 291 mensajes antes y después; la consulta tras el reinicio publica 0 | SUPERADA |
| V11 (mensaje publicado) | Clave = identificador; `source`, `ingested_at`, `mode`, `extraction_id` y evento original | Clave `ok2026wjws` = `id`; `source=usgs_feed`, `mode=live`, `extraction_id=4`, `original_event` es el `Feature` completo; el consumidor lo registró como `revised` con `produced_at` | SUPERADA |
| V1 (una hora de feed) | 60 ± 1 consultas, 0 descuadradas, originales = contenidos distintos, última ingesta < 2 min | Ver apartado V1 | Ver apartado V1 |

## Arranque

```text
$ docker compose up -d --build --wait --wait-timeout 300
 Container seismic_observatory-producer-1  Healthy
 Container seismic_observatory-consumer-1  Healthy
exit=0 17s

producer  11:31:14 Feed request 1: outcome=ok status=200 attempts=1 received=192 earthquakes=192 excluded=0 published=0
producer  11:32:14 Feed request 2: outcome=ok status=200 attempts=1 received=192 earthquakes=192 excluded=0 published=0
```

Las 192 versiones ya estaban en `core.publish_state` (las publicó el productor de la spec 002),
así que no se republican. Las dos consultas empiezan con 60 s de separación.

## V8 de la spec 002: persistencia tras reinicio

```text
antes   (current|published|messages|extractions): 273|274|291|2
$ docker compose down && docker compose up -d --wait
después (current|published|messages|extractions): 273|274|291|3
producer  11:33:03 Feed request 3: outcome=ok status=200 attempts=1 received=192 earthquakes=192 excluded=0 published=0
```

La única fila nueva es la extracción de la consulta hecha tras arrancar.

## V11: mensaje publicado

```text
producer  11:34:03 Feed request 4: outcome=ok status=200 attempts=1 received=192 earthquakes=192 excluded=0 published=1

$ docker compose exec kafka kafka-get-offsets --bootstrap-server kafka:9092 --topic earthquakes.live
earthquakes.live:0:292
$ docker compose exec kafka kafka-console-consumer --bootstrap-server kafka:9092 --topic earthquakes.live \
    --partition 0 --offset 291 --max-messages 1 --property print.key=true
(analizado con Python)
key: ok2026wjws | key == id: True
fields: ['extraction_id', 'geometry', 'id', 'ingested_at', 'mag', 'mode', 'original_event', 'place', 'properties', 'source', 'time', 'updated']
source: usgs_feed | mode: live | extraction_id: 4 | ingested_at: 2026-11-15T11:34:03.261752+00:00
original_event: Feature | same id: True

core.message_log (offset|event_id|outcome|produced_at presente): 291|ok2026wjws|revised|t
```

## V1: una hora de feed

Pendiente: se mide con la hora de funcionamiento que empieza en el arranque de las 11:31Z.
