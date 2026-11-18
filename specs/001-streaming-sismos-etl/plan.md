# Implementation Plan: Streaming de sismos con ETL y consulta geoespacial

**Branch**: `001-streaming-sismos-etl` | **Date**: 2026-11-09 | **Spec**:
`spec.md`

**Input**: Feature specification from `/specs/001-streaming-sismos-etl/spec.md`

## Summary

Construir un backend local reproducible de cinco servicios: Productor, Consumidor,
API, Kafka y PostgreSQL. El Productor obtiene periódicamente el GeoJSON de USGS y
publica features en `terremotos_raw`; el Consumidor ejecuta el WAF, enriquece
coordenadas con Natural Earth, persiste en un esquema dimensional y confirma el
offset solo tras el commit en PostgreSQL. FastAPI expone consultas filtrables y
GeoJSON para Angular/Leaflet. Un flujo separado reproduce históricos de 2025 en
`terremotos_replay`.

## Technical Context

**Language/Version**: Python 3.11; Angular/TypeScript existente en `frontend/`

**Primary Dependencies**: `aiokafka`, `requests`, `geopandas`, `shapely`,
`fastapi`, `uvicorn`, `psycopg2`, `asyncpg`, `pydantic`; imágenes
`python:3.11-slim`, `postgis/postgis:15-3.5` y `confluentinc/cp-kafka`

**Storage**: PostgreSQL 15 + PostGIS; esquema dimensional con `fact_sismos`,
`dim_geografia`, `dim_tiempo`, `cuarentena`, `ingestion_state` y
`event_versions`

**Testing**: pytest, pruebas unitarias de validación/enriquecimiento, pruebas de
contrato FastAPI, pruebas de integración con Docker Compose y replay acelerado

**Target Platform**: Linux containers ejecutados localmente mediante Docker Compose;
frontend Angular publicado en Netlify y conectado mediante ngrok

**Project Type**: sistema de streaming ETL, API REST y frontend web

**Performance Goals**: consultas de la presentación en menos de 2 segundos para el
dataset de demostración; replay al menos 10 veces más rápido que el ciclo normal de
60 segundos

**Constraints**: `docker compose up --build -d` es el único arranque backend
admitido; at-least-once; commit DB antes de commit Kafka; upsert por `id` y
`updated`; cuarentena auditable; CORS para Netlify/ngrok; sin Spark, Flink,
Kubernetes, Streamlit ni servicios Cloud adicionales

**Scale/Scope**: dataset de demostración y histórico 2025; cinco servicios locales;
filtros por país, fecha y magnitud; sin autenticación ni informes automáticos de
calidad

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Resultado | Evidencia del plan |
|---|---|---|
| Stack y despliegue local | PASS | Python, Kafka, PostgreSQL, FastAPI, Angular, Docker Compose; arranque único documentado |
| Cinco servicios locales | PASS | Productor, Consumidor, API, Kafka y PostgreSQL |
| At-least-once e idempotencia | PASS | upsert por `id`/`updated`, commit DB antes del offset |
| WAF y cuarentena | PASS | `cuarentena` con payload, origen, dimensión y motivo |
| Geoespacial | PASS | GeoPandas + Point in Polygon; mar = `Sin país asignado` |
| Calidad financiera | PASS | no se altera la memoria técnica; calidad manual y regla 1-10-100 |
| Límites de alcance | PASS | no se introducen Spark, Flink, Kubernetes, Cloud adicional, Streamlit ni informes automáticos |

No hay violaciones constitucionales que justificar.

## Project Structure

### Documentation (this feature)

```text
specs/001-streaming-sismos-etl/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api.md
│   └── events.md
└── tasks.md                 # creado por /speckit-tasks
```

### Source Code (repository root)

```text
compose.yaml
db/
├── init/
│   ├── 001_schema.sql
│   ├── 004_ingestion_state.sql
│   ├── 005_event_versions.sql
│   └── 006_mag_type.sql
└── seeds/
    └── historical_2025.jsonl
producer/
├── Dockerfile
├── requirements.txt
└── app/
    ├── __init__.py
    ├── config.py
    ├── feed.py
    ├── persistence.py
    └── main.py
consumer/
├── Dockerfile
├── requirements.txt
└── app/
    ├── __init__.py
    ├── config.py
    ├── quality.py
    ├── spatial.py
    ├── persistence.py
    └── main.py
api/
├── Dockerfile
├── requirements.txt
└── app/
    ├── __init__.py
    ├── config.py
    ├── db.py
    ├── schemas.py
    ├── queries.py
    └── main.py
frontend/
└── src/                    # cliente Angular existente; solo adaptar API si procede
tests/
├── unit/
├── contract/
└── integration/
```

**Structure Decision**: Se selecciona una estructura de servicios separados porque
cada contenedor tiene ciclo de vida y dependencias distintas, mientras `db/init`
centraliza el contrato persistente. `compose.yaml` conecta exactamente Productor,
Consumidor, API, Kafka y PostgreSQL; Zookeeper o equivalentes internos de Kafka no
se cuentan como servicios de negocio y deben seguir la imagen/configuración aprobada
para el entorno local.

### Contenedores y dependencias

- **Productor**: `python:3.11-slim`; `requests` y `aiokafka`; espera disponibilidad
  de Kafka, descarga el feed cada 60 s y publica cada feature.
- **Consumidor**: `python:3.11-slim`; `aiokafka`, `psycopg2`, `geopandas`,
  `shapely`; monta `paises.geojson` de Natural Earth en modo solo lectura.
- **API**: `python:3.11-slim`; `fastapi`, `uvicorn`, `asyncpg`, `pydantic`; aplica
  CORS a `*` en demo o a una lista configurable de dominios Netlify/ngrok.
- **Kafka**: `confluentinc/cp-kafka`; topics `terremotos_raw` y
  `terremotos_replay`, con retención suficiente para replay local.
- **PostgreSQL**: `postgis/postgis:15-3.5`; volumen persistente e inicialización
  idempotente desde `db/init/001_schema.sql`.

## Phase 0: Outline & Research

La investigación resuelve el uso de imágenes ligeras, la coordinación DB/Kafka, la
semántica de upsert, el diseño dimensional, la clasificación marítima y el contrato
GeoJSON/CORS. Las decisiones consolidadas están en [research.md](./research.md).

## Phase 1: Design & Contracts

- [data-model.md](./data-model.md) define dimensiones, hechos, cuarentena, claves,
  validaciones, relaciones, historial de versiones e índices B-Tree.
- [contracts/api.md](./contracts/api.md) define endpoints, filtros, errores, CORS y
  GeoJSON.
- [contracts/events.md](./contracts/events.md) define el evento Kafka, topics,
  origen, replay y orden transaccional.
- [quickstart.md](./quickstart.md) define la validación reproducible con Compose,
  datos inválidos, idempotencia, consultas y replay.

## Constitution Check — Post-Design

| Gate | Resultado | Verificación post-diseño |
|---|---|---|
| Reproducibilidad | PASS | quickstart usa exclusivamente `docker compose up --build -d` |
| Transaccionalidad | PASS | events.md exige commit PostgreSQL antes de `consumer.commit()` |
| Cuarentena | PASS | data-model.md tipa siete dimensiones de calidad y motivo |
| Integración espacial | PASS | `dim_geografia` conserva país/continente/subregión y regla marítima |
| Consultas | PASS | índices B-Tree para fecha y país documentados |
| CORS | PASS | api.md especifica middleware y orígenes configurables |
| Límites | PASS | no se añaden tecnologías prohibidas ni automatización de informes |

**Gate final: PASS.**

## Complexity Tracking

No aplica: el diseño no introduce violaciones constitucionales ni componentes
innecesarios fuera de los cinco servicios locales.
