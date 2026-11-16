# Recuperación de huecos (US4: V8)

- Observado (UTC): 2026-11-15T19:02Z a 2026-11-15T19:05Z
- Rama y commit: 003-usgs-ingestion @ 1121109
- Equipo: MINGW64_NT-10.0-26200 3.5.4-cbe555e0.x86_64 x86_64
- Motor: Docker 29.1.3 (Docker Desktop (containerized)), Compose 2.40.3-desktop.1; recursos del motor: 12 CPU, 7,6 GiB
- Ejecutado con la confirmación expresa de la usuaria (T038), porque modifica marcas de tiempo de
  la base local.

**La parada es simulada.** En lugar de esperar 36 horas, se restaron 36 horas al `requested_at`
de las consultas del feed ya registradas, y se restauraron al terminar. La recuperación, en
cambio, es real: consulta el catálogo de USGS y los eventos recuperados se conservan.

| | V8 |
|---|---|
| Esperado | Aviso «Ingestion gap detected» en menos de un minuto con la orden exacta; el feed sigue consultándose; tras ejecutar la orden, las consultas constan como `gap_recovery`, los eventos del periodo están en `core` sin duplicados y `--gaps` da el hueco por recuperado |
| Observado | Aviso 2 s después de arrancar, con la orden; consulta del feed `ok` en el mismo segundo; la orden recuperó 128 eventos de todas las magnitudes (128 declarados, diferencia 0); 128 eventos distintos en `core` en el periodo; consultas `gap_recovery`; `--gaps`: «recuperado»; fechas restauradas exactamente |
| Resultado | SUPERADA |

## 1. Estado antes de simular

```text
consultas del feed (source = usgs_feed): max_id=214 · filas=115
min=2026-11-15 11:31:14.207868+00 · max=2026-11-15 19:02:23.889849+00 · suma_epoch=206397546346
$ docker compose stop producer
```

## 2. Simulación de la parada

```sql
UPDATE core.extraction SET requested_at = requested_at - interval '36 hours'
WHERE source = 'usgs_feed' AND extraction_id <= 214;
-- UPDATE 115 · desplazadas: min=2026-11-13 23:31:14Z, max=2026-11-14 07:02:23Z
```

## 3. Arranque: aviso y feed

```text
$ docker compose start producer          (19:02:35Z)
19:02:37.394Z WARNING Ingestion gap detected: last successful feed request at 2026-11-14T07:02:23Z;
  events between 2026-11-14T06:02:00Z and 2026-11-14T20:03:00Z are not covered by the feed.
  Recover with: docker compose run --rm catalog-loader --purpose gap_recovery
  --start 2026-11-14T06:02:00Z --end 2026-11-14T20:03:00Z
19:02:37.396Z INFO Purged 0 raw payload(s) not seen for more than 7 days
19:02:37.510Z INFO Feed request 215: outcome=ok status=200 attempts=1 received=185 earthquakes=185 excluded=0 published=0
```

El periodo va de la última consulta correcta menos 60 minutos de margen (06:02) a 24 horas antes
del arranque más 60 minutos (20:03). El aviso no lanza nada: el feed empieza igual.

## 4. Huecos pendientes y recuperación

```text
$ docker compose run --rm catalog-loader --gaps
2026-11-14T06:02:00Z → 2026-11-14T20:03:00Z  PENDIENTE
    docker compose run --rm catalog-loader --purpose gap_recovery --start 2026-11-14T06:02:00Z --end 2026-11-14T20:03:00Z

$ docker compose run --rm catalog-loader --purpose gap_recovery --start 2026-11-14T06:02:00Z --end 2026-11-14T20:03:00Z
Periodo 2026-11-14T06:02:00Z → 2026-11-14T20:03:00Z · todas las magnitudes · todos los tipos
Intervalo                                     Declarados  Recibidos Terremotos Excluidos Publicados  Fichero
2026-11-14 06:02:00 → 2026-11-14 20:03:00            128        128        128         0         24  descargado
Repetidos entre intervalos: 0
Eventos distintos:      128
Declarados por USGS:    128   (recuento del periodo completo al terminar)
Diferencia:             0
exit=0   real 0m3.152s
```

## 5. Comprobaciones

```text
eventos en core.event_current con event_time en el periodo: 128 · distintos: 128 · de magnitud < 2,5: 98
  por procedencia: usgs_feed 103 · usgs_catalog 25
mensajes del catálogo procesados en esta recuperación: new 3 · revised 21
cuarentena nueva: 0

extracciones gap_recovery:
 tipo  | outcome | record_count | published_count
-------+---------+--------------+-----------------
 count | ok      |          128 |
 query | ok      |          128 |              24
 count | ok      |          128 |                     (recuento final del periodo)

$ docker compose run --rm catalog-loader --gaps
2026-11-14T06:02:00Z → 2026-11-14T20:03:00Z  recuperado
```

Como la parada es simulada, gran parte del periodo ya la había traído el feed esta mañana (su
ventana de 24 h cubría desde el 14-11 a las 11:31Z): de los 128 eventos solo se publicaron 24,
3 nuevos y 21 revisiones, porque el catálogo tenía versiones más recientes. Los demás tenían en
`publish_state` una versión igual o posterior y no se republicaron. Los 128 están en `core` una
sola vez. Uno de los 25 con procedencia `usgs_catalog` ya venía de la carga de 2026 (M ≥ 4).
Ningún evento fue a cuarentena, aunque 98 tienen magnitud menor de 2,5: todos traían magnitud.

## 6. Restauración

```sql
UPDATE core.extraction SET requested_at = requested_at + interval '36 hours'
WHERE source = 'usgs_feed' AND extraction_id <= 214;
-- UPDATE 115
```

```text
después: max_id=214 · filas=115 · min=2026-11-15 11:31:14.207868+00 · max=2026-11-15 19:02:23.889849+00
         suma_epoch=206397546346          (idénticos a los del paso 1)

$ docker compose run --rm catalog-loader --gaps
No ingestion gaps: the feed has never been stopped for more than 24 hours.
```

Las extracciones `gap_recovery` y los eventos recuperados son reales y se conservan.
