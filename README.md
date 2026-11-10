# Observatorio Sísmico

Sistema local reproducible de streaming ETL para ingerir, validar, enriquecer y
consultar terremotos del feed GeoJSON de USGS. El proyecto implementa una
arquitectura dimensional sobre PostgreSQL/PostGIS, mensajería Kafka y una API
FastAPI consumida por un mapa Angular/Leaflet.

## 1. Objetivo académico

El sistema demuestra un pipeline de datos con semántica **at-least-once**,
calidad auditable e integración espacial:

- Los eventos originales se publican en Kafka antes de ser procesados.
- El consumidor aplica un WAF de calidad y nunca descarta silenciosamente un
  evento inválido.
- Los eventos válidos se enriquecen con Point in Polygon sobre Natural Earth.
- PostgreSQL se confirma antes que el offset Kafka.
- El upsert por `external_id` solo acepta una versión con `updated` posterior.
- Los históricos de 2025 se reproducen en un topic aislado y trazable.

## 2. Arquitectura de cinco servicios

`docker compose up --build -d` levanta exactamente los cinco servicios locales:

| Servicio | Responsabilidad | Tecnología |
|---|---|---|
| `producer` | Descarga USGS cada 60 segundos y publica features | Python, `requests`, `aiokafka` |
| `consumer` | WAF, cuarentena, enriquecimiento y persistencia | Python, GeoPandas, Shapely, `psycopg2` |
| `api` | Consultas filtrables, estadísticas y GeoJSON | FastAPI, `asyncpg`, Pydantic |
| `kafka` | Topics `terremotos_raw` y `terremotos_replay` | Kafka KRaft |
| `postgres` | Modelo dimensional y PostGIS | PostgreSQL 15 + PostGIS |

Angular/Leaflet se mantiene como cliente web, no como contenedor adicional del
backend. Netlify y ngrok son opcionales para una demostración remota.

## 3. Decisiones de diseño

### WAF de calidad y cuarentena

Cada evento atraviesa validaciones de completitud, validez, exactitud,
consistencia, oportunidad y unicidad. Los fallos se insertan en `cuarentena`
con payload original, topic, partición, offset, código estable, detalle y
timestamp. Por ejemplo, un `mag` nulo es un fallo de **Completitud** y una
latitud fuera de `[-90, 90]` es un fallo de **Validez**.

### Transaccionalidad e idempotencia

El consumidor desactiva el auto-commit de Kafka. Para cada mensaje:

1. Parseo y WAF.
2. Cuarentena o enriquecimiento.
3. Commit de la transacción PostgreSQL.
4. `consumer.commit()` del offset Kafka.

El upsert está condicionado por `excluded.updated > fact_sismos.updated`.
Si el proceso falla antes del commit de base de datos, el offset queda sin
confirmar. Si falla después, el reprocesamiento es seguro.

### GeoPandas y eventos marítimos

El catálogo Natural Earth se carga una vez por consumidor y cada punto se cruza
con polígonos terrestres. Si no existe intersección, el país es exactamente
`Sin país asignado`; no se imputa el país más cercano.

## 4. Arranque y configuración

Requisitos: Docker Engine y Docker Compose.

1. Copiar `.env.example` a `.env` y establecer credenciales locales seguras.
2. Arrancar el backend:

   ```powershell
   docker compose up --build -d
   docker compose ps
   ```

3. Esperar los healthchecks de Kafka y PostgreSQL. API, Productor y Consumidor
   dependen de esos servicios saludables.

Variables principales:

| Variable | Uso |
|---|---|
| `DATABASE_DSN` | DSN de PostgreSQL para Consumidor |
| `KAFKA_BOOTSTRAP_SERVERS` | Broker Kafka |
| `KAFKA_RAW_TOPIC` | Topic de ingesta USGS |
| `KAFKA_REPLAY_TOPIC` | Topic de histórico |
| `KAFKA_GROUP_ID` | Grupo del consumidor |
| `USGS_FEED_URL` | Feed GeoJSON consultado |
| `PRODUCER_INTERVAL_SECONDS` | Periodicidad de ingesta |
| `COUNTRIES_GEOJSON_PATH` | Catálogo Natural Earth montado |
| `CORS_ORIGINS` | `*` en demo o lista separada por comas |

## 5. API

Base URL: `http://localhost:8000/api`.

```powershell
curl "http://localhost:8000/api/eventos?format=geojson&min_magnitude=4"
curl "http://localhost:8000/api/estadisticas/paises"
curl "http://localhost:8000/api/estadisticas/timeline?bucket=month"
```

`/eventos` acepta `country`, `date_from`, `date_to`, `min_magnitude`,
`max_magnitude`, `limit` y `offset`. Con `format=geojson` o
`Accept: application/geo+json` devuelve un `FeatureCollection` con puntos
`[longitude, latitude, depth_km]`.

Los rangos incompatibles devuelven HTTP 400. La indisponibilidad de PostgreSQL
devuelve HTTP 503 sin exponer detalles sensibles. CORS permite `GET` y
`OPTIONS`, incluyendo el header `ngrok-skip-browser-warning`.

## 6. Replay histórico 2025

El lote reproducible está en
[`db/seeds/historical_2025.jsonl`](db/seeds/historical_2025.jsonl). Incluye
eventos válidos, un punto marítimo, fallos WAF y dos versiones del mismo ID.

Publicar a velocidad acelerada:

```powershell
docker compose run --rm producer python -m app.replay `
  --path /data/seeds/historical_2025.jsonl --rate 10
```

El script rechaza eventos que no pertenezcan a 2025, conserva
`source_topic=terremotos_replay` y registra el contador de publicación. El
consumidor procesa ambos topics mediante el mismo WAF, cruce espacial y upsert.

## 7. Validación reproducible

La guía completa de evaluación está en
[`specs/001-streaming-sismos-etl/quickstart.md`](specs/001-streaming-sismos-etl/quickstart.md).
Incluye:

- Evento válido y evento marítimo.
- Cuarentena por magnitud nula y coordenada inválida.
- Idempotencia con versiones antiguas y nuevas.
- Orden commit PostgreSQL → offset Kafka.
- Consultas API, GeoJSON, filtros y CORS.
- Replay acelerado y trazabilidad por topic.

Métricas operativas se escriben en los logs estructurados:

- Productor: publicados por ciclo y reintentos de conexión/publicación.
- Consumidor: procesados, puestos en cuarentena y lag observado por offset.
- API: filas devueltas por endpoint y filtros aplicados.

La revisión de calidad aplica la regla 1-10-100 de forma manual: prevenir
errores mediante contratos y validación temprana, detectarlos en el WAF antes de
persistir y reservar la corrección costosa para los eventos ya observados en
producción. No se generan informes automáticos de calidad.

Para detener servicios sin borrar evidencia:

```powershell
docker compose down
```

No usar `docker compose down -v` durante las pruebas de idempotencia o replay.

## 8. Límites tecnológicos

El proyecto usa únicamente el stack aprobado: Python, Kafka, PostgreSQL/PostGIS,
FastAPI, Docker Compose, Angular y Leaflet. No contiene ni requiere Spark,
Flink, Kubernetes, Streamlit ni servicios Cloud adicionales.
