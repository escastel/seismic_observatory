# Contrato de ejecución

Nombres de servicio, red, topics, variables y semántica de salud que todos los componentes
comparten.

## Servicios de Compose

| Servicio | Imagen | Puerto en el equipo | Depende de (sano) | Salud |
|---|---|---|---|---|
| `postgres` | `postgres:16.4` | ninguno | — | conexión TCP y modelo creado |
| `kafka` | `confluentinc/cp-kafka:7.7.1` | ninguno | — | el broker responde a una consulta de API |
| `producer` | propia | ninguno | `kafka`, `postgres` | latido reciente |
| `consumer` | propia | ninguno | `kafka`, `postgres` | latido reciente |
| `api` | propia | `127.0.0.1:8000` | `postgres` | `GET /api/salud` responde |
| `tunnel` (perfil `tunnel`) | `ngrok/ngrok:3.39.13-alpine` | ninguno | `api` | — |

- `docker compose up --build -d` arranca los cinco primeros.
- `docker compose --profile tunnel up -d` añade el túnel hacia `http://api:8000`.
- Todos usan `restart: unless-stopped`.
- Volúmenes con nombre: `postgres_data` y `kafka_data`.

## Direcciones internas

| Desde | Hacia | Dirección |
|---|---|---|
| productor, consumidor | Kafka | `kafka:9092` |
| productor, consumidor, API | PostgreSQL | `postgres:5432` |
| túnel | API | `http://api:8000` |

Kafka expone un único listener interno. No hay acceso a Kafka ni a PostgreSQL desde el equipo;
las herramientas se ejecutan con `docker compose exec` o con `compose.dev.yaml`.

## Topics

| Topic | Contenido | Esquema de destino | Particiones | Retención |
|---|---|---|---|---|
| `earthquakes.live` | Novedades del feed de 24 horas | `core` | 1 | 7 días |
| `earthquakes.catalog` | Carga histórica y recuperación de huecos | `core` | 1 | 7 días |
| `earthquakes.replay` | Reproducción acelerada | `replay` | 1 | 7 días |

Clave del mensaje: `event_id`. Los topics los crean productor y consumidor al arrancar; la
creación automática del broker está desactivada.

Consumo: confirmación automática desactivada; un grupo sin offsets confirmados empieza por el
principio del topic; tras un fallo de procesamiento se reintenta el mismo mensaje y no se
confirma ningún offset posterior.

## Variables de entorno

| Variable | Usada por | Significado |
|---|---|---|
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | `postgres` | Base y propietario |
| `DB_WRITER_PASSWORD` | `postgres`, productor, consumidor | Contraseña de `observatory_writer` |
| `DB_READER_PASSWORD` | `postgres`, API | Contraseña de `observatory_reader` |
| `DB_HOST`, `DB_PORT` | servicios Python | Destino de la base (`postgres`, `5432`) |
| `KAFKA_BOOTSTRAP_SERVERS` | productor, consumidor | `kafka:9092` |
| `KAFKA_TOPIC_LIVE`, `KAFKA_TOPIC_CATALOG`, `KAFKA_TOPIC_REPLAY` | productor, consumidor | Nombres de los topics |
| `KAFKA_GROUP_ID` | consumidor | Grupo de consumo |
| `KAFKA_RETENTION_HOURS` | `kafka`, creación de topics | 168 por defecto |
| `USGS_FEED_URL` | productor | Feed `all_day.geojson` |
| `PRODUCER_INTERVAL_SECONDS` | productor | 60 por defecto |
| `RAW_PAYLOAD_RETENTION_DAYS` | productor | 7 por defecto |
| `COUNTRIES_GEOJSON_PATH` | consumidor | Ruta del catálogo dentro del contenedor |
| `CORS_ORIGINS` | API | Lista de orígenes exactos separados por comas (el de Netlify y `http://localhost:4200`); sin comodín |
| `NGROK_AUTHTOKEN`, `NGROK_DOMAIN` | `tunnel` | Solo en `.env` local, nunca en Git |

`.env.example` contiene todas con valores de ejemplo no secretos. Un servicio que no encuentra
una variable obligatoria termina con un mensaje que la nombra.

## Salud y reintentos

- Productor y consumidor actualizan un fichero de latido tras cada ciclo correcto. La
  comprobación falla si el latido tiene más de tres intervalos de antigüedad.
- Conexiones a Kafka y PostgreSQL: reintento con espera exponencial desde 1 s hasta un máximo de
  30 s, sin límite de intentos, registrando cada fallo.
- `GET /api/salud` responde aunque la base no esté disponible, indicando estado degradado; nunca
  incluye credenciales.

## Imágenes Python

- Base `python:3.11.10-slim-bookworm`, usuario sin privilegios.
- Contexto de construcción: la raíz del repositorio; cada imagen copia `common/` y su servicio.
- Dependencias instaladas desde un `requirements.txt` con todas las versiones fijadas.
- Ninguna imagen contiene conjuntos de datos: los ficheros de `data/` se montan en ejecución.
