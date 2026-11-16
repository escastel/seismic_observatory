# Feed en vivo con procedencia (US1: V1, V8 de la spec 002, V11)

- Observado (UTC): 2026-11-15T11:31Z a 2026-11-15T11:35Z; V1 de 17:56Z a 18:57Z
- Rama y commit: 003-usgs-ingestion @ 1614271 más el ciclo nuevo del productor (sin commit al observar)
- Equipo: MINGW64_NT-10.0-26200 3.5.4-cbe555e0.x86_64 x86_64
- Motor: Docker 29.1.3 (Docker Desktop (containerized)), Compose 2.40.3-desktop.1; recursos del motor: 12 CPU, 7,6 GiB

## Resumen

| Escenario | Esperado | Observado | Resultado |
|---|---|---|---|
| Arranque con el productor nuevo | Cinco servicios sanos; cada consulta registrada | Cinco `healthy` en 17 s; «Feed request 1/2: outcome=ok … received=192 earthquakes=192 excluded=0» | SUPERADA |
| V8 de la spec 002 (reinicio) | Mismo recuento; no se republica nada | 273 eventos, 274 publicados y 291 mensajes antes y después; la consulta tras el reinicio publica 0 | SUPERADA |
| V11 (mensaje publicado) | Clave = identificador; `source`, `ingested_at`, `mode`, `extraction_id` y evento original | Clave `ok2026wjws` = `id`; `source=usgs_feed`, `mode=live`, `extraction_id=4`, `original_event` es el `Feature` completo; el consumidor lo registró como `revised` con `produced_at` | SUPERADA |
| V1 (una hora de feed) | 60 ± 1 consultas, 0 descuadradas, originales = contenidos distintos, última ingesta < 2 min | 60 consultas (57 `ok`, 3 `not_modified`), 0 descuadradas, 17 originales para 17 contenidos distintos, separación entre 59,996 s y 60,059 s, última ingesta hace 10 s | SUPERADA |

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

**Primer intento, no válido.** Medido sobre 11:34Z–12:34Z: solo 27 consultas, porque el equipo
o Docker se detuvieron a las 12:00:03Z y no volvieron hasta las 17:54Z. Las 27 que hubo eran
correctas (0 descuadradas, 16 originales para 16 contenidos distintos, separación de 60 s), pero
no forman una hora seguida, así que se repitió la medición. La parada de casi 6 horas es menor de
24 h y no deja hueco: el feed la cubre.

**Medición válida.** El productor se reconstruyó con el código final a las 17:55:48Z (purga y
aviso de huecos incluidos) y se midió la ventana fija 17:56Z–18:56Z, sin reinicios ni
suspensión del equipo. Consultas ejecutadas a las 18:57:05Z:

```text
 outcome      | count
--------------+-------
 not_modified |     3
 ok           |    57

 descuadradas | contenidos_distintos | publicadas | excluidos
--------------+----------------------+------------+-----------
            0 |                   17 |         13 |         0

 originales_de_las_consultas: 17          (un original por contenido distinto)

 menor_separacion | mayor_separacion
------------------+------------------
 00:00:59.996305  | 00:01:00.059208

 antiguedad_ultima_ingesta: 00:00:10.102351
```

Las 3 respuestas `not_modified` (304) confirman que la petición condicional funciona cuando USGS
no ha regenerado el feed. Ningún elemento de la hora era de otro tipo, así que no hubo
exclusiones.
