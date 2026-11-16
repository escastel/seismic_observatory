# Reiniciar el consumidor a mitad de un lote (V3 · SC-006)

- Observado (UTC): 2026-11-16T13:20Z a 2026-11-16T13:24Z
- Rama y commit: 004-consumer-quality @ 1d469f4
- Equipo: MINGW64_NT-10.0-26200 3.5.4-cbe555e0.x86_64 x86_64
- Motor: Docker 29.1.3 (Docker Desktop (containerized)), Compose 2.40.3-desktop.1; recursos del motor: 12 CPU, 7,6 GiB

| | V3 |
|---|---|
| Esperado | Matar el consumidor a mitad de un lote de 1.000 mensajes y reiniciarlo termina con los mismos recuentos que sin reinicio (1.000 eventos, 1.000 versiones, 1.000 mensajes, sin duplicados) |
| Observado | Muerto con `docker kill` tras procesar 357 de 1.000; tras reiniciar terminó los 1.000: 1.000 eventos, 1.000 versiones, 1.000 filas de registro, 1.000 identificadores distintos, 0 cuarentena, offsets 610 a 1609 sin huecos |
| Resultado | SUPERADA (prueba de aceptación §11 «Reiniciar consumidor») |

## Procedimiento

```bash
docker compose stop consumer producer          # nada procesa mientras se publica el lote
docker compose -f compose.yaml -f compose.dev.yaml run --rm -e KAFKA_BOOTSTRAP_SERVERS=kafka:9092 \
  -e KAFKA_TOPIC_LIVE=earthquakes.live -e KAFKA_TOPIC_CATALOG=earthquakes.catalog \
  -e KAFKA_TOPIC_REPLAY=earthquakes.replay tests python -m tests.synthetic.inject --batch 1000
docker compose start consumer
docker logs -f seismic_observatory-consumer-1 | grep -m1 "offset=941 " ; docker kill seismic_observatory-consumer-1
docker compose start consumer                  # reanuda desde el último offset confirmado
docker compose start producer
```

```text
offset final antes del lote: 610 · después: 1610 (1.000 mensajes en el topic)
Publicados 1000, omitidos (ya constan) 31
consumidor matado al llegar al offset 941
procesados al matar: eventos=357 mensajes_log=357
tras reiniciar: mensajes_log=1000
```

## Recuentos finales

```text
 eventos | versiones | mensajes | ids_distintos | cuarentena
---------+-----------+----------+---------------+------------
    1000 |      1000 |     1000 |          1000 |          0
 outcome new: 1000 · marcados `synthetic`: 1000
 desde 610 · hasta 1609 · n 1000 · huecos 0
```

Los mensajes que el consumidor ya había escrito pero cuyo offset no llegó a confirmar se vuelven
a procesar tras el reinicio, y la regla de versiones y la clave del registro los absorben sin
crear filas nuevas: por eso los recuentos son los mismos que sin reinicio. Todo el lote es
sintético (prefijo `synthetic-batch-`) y queda fuera de los recuentos reales.
