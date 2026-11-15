# Quickstart: validar la ingesta

Guía para comprobar la funcionalidad de extremo a extremo una vez implementada. Cada escenario
indica la historia de usuario y el criterio de éxito que evidencia. Los resultados observados se
guardan en `docs/evidence/003/` con la skill `verify-stack`.

Referencias: [data-model.md](data-model.md), [contracts/catalog-loader.md](contracts/catalog-loader.md),
[contracts/messages.md](contracts/messages.md), [contracts/runtime.md](contracts/runtime.md).

## Requisitos

- Sistema de la spec 002 levantado: `docker compose up --build -d`, cinco servicios sanos.
- `.env` con las variables nuevas de `.env.example`.
- Conexión a Internet para los escenarios con la fuente real (V1, V4 a V7, V10).
- Las consultas SQL se ejecutan dentro del contenedor:

  ```bash
  docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
  ```

## V1. Una hora de feed con procedencia (US1 · SC-001, SC-002, SC-009)

Dejar el sistema una hora y consultar:

```sql
SELECT outcome, count(*) FROM core.extraction
WHERE source = 'usgs_feed' AND requested_at > now() - interval '1 hour' GROUP BY 1;

SELECT count(*) FILTER (WHERE record_count <> earthquake_count + excluded_count) AS descuadradas,
       count(DISTINCT content_sha256) AS contenidos_distintos
FROM core.extraction
WHERE source = 'usgs_feed' AND outcome = 'ok' AND requested_at > now() - interval '1 hour';

SELECT count(*) FROM core.raw_payload WHERE last_seen_at > now() - interval '1 hour';

SELECT now() - max(requested_at) AS antiguedad FROM core.extraction
WHERE source = 'usgs_feed' AND outcome IN ('ok', 'not_modified');
```

Esperado: 60 ± 1 consultas entre `ok` y `not_modified`; 0 descuadradas; originales observados en
la hora = contenidos distintos; antigüedad de la última ingesta menor de dos minutos.

## V2. Exclusiones y elementos no identificables (US1)

Con la fuente simulada sirviendo una respuesta que contiene un terremoto, una voladura
(`quarry blast`) y un elemento sin `id`:

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests pytest tests/db/test_feed_cycle.py -v
```

Esperado: 1 publicado; 1 fila en `excluded_event` con su tipo, motivo y extracción, que no se
repite en un segundo ciclo; la extracción indica 3 recibidos, 1 terremoto y 2 excluidos, y
`error_detail` describe el elemento sin identificador.

## V3. Fallos de la fuente (US3 · SC-008)

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests \
  pytest tests/unit/test_usgs_client.py tests/db/test_feed_failures.py -v
```

Esperado, para saturación con `Retry-After`, error de servidor, tiempo agotado, cuerpo ilegible
y estructura no válida: una fila de extracción con su resultado, intentos y detalle; espera no
inferior a la indicada; nada publicado ni borrado; el ciclo siguiente correcto;
`last_ingestion` sin avanzar durante los fallos.

Con el sistema real: arrancar un productor apuntando a la fuente simulada y observar que sigue
`healthy` mientras la fuente falla.

```bash
docker compose -f compose.yaml -f compose.dev.yaml --profile test up -d usgs-stub
docker compose -f compose.yaml -f compose.dev.yaml run --rm -e USGS_FEED_URL=http://usgs-stub:8080/feed/fail-503 producer
```

## V4. Carga obligatoria de 2025 (US2 · SC-003, SC-006, SC-011)

```bash
time docker compose run --rm catalog-loader
```

Esperado: 12 intervalos mensuales; resumen con diferencia 0 frente al total declarado por USGS
(18.302 el 2026-11-15; puede variar si USGS revisa el catálogo); menos de 15 minutos hasta
que la orden termina, sin contar el tiempo posterior del consumidor. Después,
cuando el consumidor haya terminado:

```sql
SELECT count(*) FROM core.event_current
WHERE event_time >= '2025-01-01' AND event_time < '2026-01-01' AND magnitude >= 4;

SELECT source, count(*) FROM core.event_current
WHERE event_time >= '2025-01-01' AND event_time < '2026-01-01' GROUP BY 1;

SELECT count(*) FROM replay.event_current;
```

Esperado: el primer recuento coincide con «eventos distintos» del resumen (o la diferencia está
en cuarentena con su motivo); procedencia `usgs_catalog`; 0 filas en `replay`.

Ficheros y huellas:

```bash
git status --short data/            # sin salida: nada de data/ entra en Git
ls data/usgs/catalog/
( cd data && sha256sum usgs/catalog/*.geojson )
```

```sql
SELECT file_path, content_sha256, byte_size FROM core.raw_payload WHERE encoding = 'file' ORDER BY 1;
```

Esperado: cada huella calculada coincide con la registrada.

## V5. Repetir y reanudar la carga (US2 · SC-004, SC-005)

```bash
docker compose run --rm catalog-loader            # segunda ejecución completa
```

Esperado: ningún intervalo descargado de nuevo, 0 publicados, los mismos recuentos en
`event_current` y `event_version`.

Reanudación: sobre una base recreada, lanzar la carga, interrumpirla con Ctrl+C hacia la mitad y
volver a lanzarla. Esperado: continúa, y los recuentos finales son los de V4.

## V6. Subdivisión sin truncar (US2)

```bash
docker compose run --rm catalog-loader --dry-run --all-magnitudes --all-types \
  --start 2026-09-01 --end 2026-11-01
```

Esperado: los meses con más de 20.000 eventos aparecen divididos en intervalos menores, cada uno
con un recuento por debajo del máximo; no se descarga ni publica nada. La prueba automática
`tests/unit/test_catalog_plan.py` cubre el caso de un intervalo imposible de subdividir.

## V7. Ampliación con 2026 (US6 · SC-012)

```bash
docker compose run --rm catalog-loader --start 2026-01-01 --end <hoy>
```

Esperado: diferencia 0 con el total declarado; el recuento de 2025 de V4 no cambia; los eventos
recientes que también trae el feed existen una sola vez.

## V8. Hueco tras una parada (US4 · SC-007)

1. Parar el productor: `docker compose stop producer`.
2. Simular la antigüedad sin esperar 36 horas, retrasando las consultas registradas:

   ```sql
   UPDATE core.extraction SET requested_at = requested_at - interval '36 hours'
   WHERE source = 'usgs_feed';
   ```

   (solo en la base local de pruebas, como propietario; anotar que es una simulación).
3. Arrancar: `docker compose start producer` y leer `docker compose logs --tail 20 producer`.
4. Ejecutar la orden que muestra el aviso y, después, `docker compose run --rm catalog-loader --gaps`.

Esperado: aviso «Ingestion gap detected» en menos de un minuto con la orden exacta; el feed
sigue consultándose; tras la recuperación, las consultas constan con propósito `gap_recovery`,
los eventos del periodo están en `core` sin duplicados y `--gaps` indica el hueco como
recuperado.

5. Restaurar las fechas simuladas sumando 36 horas a las mismas filas, para no distorsionar el
   perfil de la fuente (V10).

## V9. Purga de originales (US5 · SC-010)

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests pytest tests/db/test_purge_cycle.py -v
```

Esperado: se eliminan los cuerpos no observados desde hace más de la retención; se conservan los
recientes, las referencias a ficheros y todas las extracciones; el productor registra en el log
cuántos eliminó. Con el sistema real, tras 24 horas de funcionamiento:

```sql
SELECT count(*) FROM core.raw_payload
WHERE body IS NOT NULL AND last_seen_at < now() - interval '8 days';   -- esperado: 0
```

## V10. Descripción de la fuente (FR-036a · SC-013)

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m tests.analysis.source_profile
```

Esperado: `docs/evidence/003/source-profile.md` con, para cada campo utilizado del feed y del
catálogo, tipos observados, porcentaje de ausencias y rango; frecuencia real de cambio del feed;
errores registrados; latencia de las consultas y retraso de publicación. La memoria
(`docs/report.md`) lo resume.

## V11. Mensaje publicado (FR-008a)

```bash
docker compose exec -T kafka kafka-console-consumer --bootstrap-server kafka:9092 \
  --topic earthquakes.live --from-beginning --max-messages 1 --property print.key=true
```

Esperado: clave igual al identificador del evento; el valor incluye `source`, `ingested_at`,
`mode`, `extraction_id` y `original_event`, según [contracts/messages.md](contracts/messages.md).

## V12. Nada cambia fuera del alcance (FR-035)

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests pytest tests/db tests/unit tests/contract -q
git diff 002-platform-data-model -- db/sql consumer api
```

Esperado: todas las pruebas de la spec 002 siguen en verde; sin cambios en `db/sql/`, en las
reglas del consumidor ni en la API, salvo los justificados por escrito en el plan.
