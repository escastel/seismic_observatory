# Observatorio Sísmico

Sistema local y reproducible de streaming ETL que ingiere, valida, enriquece y sirve los
terremotos del feed GeoJSON de USGS: productor → Kafka → consumidor → PostgreSQL → API FastAPI,
consultada por un panel Angular/Leaflet publicado en Netlify a través de un túnel ngrok.

## 1. Objetivo académico

El sistema demuestra un pipeline de datos con semántica **al menos una vez**, idempotente y
versionado, con calidad auditable e integración espacial:

- Los eventos originales se publican en Kafka antes de procesarse.
- El consumidor nunca descarta en silencio un evento inválido: lo guarda en cuarentena con el
  mensaje original y todos los motivos.
- Los eventos válidos se cruzan con los polígonos de Natural Earth (punto en polígono).
- La transacción de PostgreSQL se confirma antes que el offset de Kafka.
- Una versión antigua de un evento nunca sustituye a una más reciente, y cada versión queda en
  el historial.
- La reproducción acelerada del histórico escribe en un esquema propio, separado de los datos
  reales.

## 2. Arquitectura

`docker compose up --build -d` levanta exactamente cinco servicios:

| Servicio | Responsabilidad | Tecnología |
|---|---|---|
| `producer` | Consulta USGS cada 60 s y publica las versiones nuevas | Python, `requests`, `aiokafka`, `asyncpg` |
| `consumer` | Validación, cuarentena, cruce espacial y persistencia | Python, GeoPandas, Shapely, `aiokafka`, `asyncpg` |
| `api` | Consultas filtrables, estadísticas y GeoJSON | FastAPI, Pydantic, `asyncpg` |
| `kafka` | Topics `earthquakes.live`, `earthquakes.catalog` y `earthquakes.replay` | Kafka 3.7 en modo KRaft |
| `postgres` | Modelo de datos (esquemas `core` y `replay`) | PostgreSQL 16 |

El túnel ngrok es un sexto servicio opcional, `tunnel`, que solo arranca con
`--profile tunnel` (apartado 5). El panel Angular no es un contenedor: se publica en Netlify
desde `frontend/`.

El modelo de datos, sus decisiones y el diccionario están en
[specs/002-platform-data-model/data-model.md](specs/002-platform-data-model/data-model.md) y en
[docs/report.md](docs/report.md); la interfaz que usan los servicios, en
[contracts/database.md](specs/002-platform-data-model/contracts/database.md).

### Red y superficie expuesta

Solo la API publica un puerto, y únicamente en el propio equipo (`127.0.0.1:8000`). Kafka tiene
un único listener interno (`kafka:9092`) y PostgreSQL no publica ninguno: nada fuera de la red de
Compose puede escribir en el broker ni en la base. Es una decisión deliberada: la API es la única
pieza que llega a Internet, a través del túnel, y se conecta con un rol de solo lectura
(`observatory_reader`). Las herramientas que necesitan Kafka o PostgreSQL se ejecutan dentro de
la red con `docker compose exec` o con el servicio de pruebas de `compose.dev.yaml`.

### Entrega y versiones

El consumidor desactiva la confirmación automática de offsets. Por cada mensaje abre una
transacción, aplica la versión con `apply_event_version` (o la guarda en cuarentena), anota el
mensaje en `message_log`, confirma la transacción y solo entonces confirma el offset. Si algo
falla, reintenta el mismo mensaje con espera creciente y no confirma ningún offset posterior. Un
grupo de consumo nuevo empieza por el principio del topic.

La función `apply_event_version` devuelve `new`, `revised`, `stale` o `duplicate`: el estado
actual solo cambia con un `updated` posterior al guardado, y reprocesar un mensaje no cambia
nada.

### Eventos sin país

Si el punto no cae dentro de ningún polígono del catálogo, el evento se guarda con país nulo y
el panel muestra «Sin país asignado»; nunca se imputa el país más cercano.

## 3. Requisitos y versiones

- Docker Engine 26 o posterior con Docker Compose v2 (en Windows y macOS, Docker Desktop).
- Unos 3 GB libres para las imágenes y 8 GB de RAM.
- Git. En Windows, las órdenes de este documento se escriben para Git Bash.

Imágenes fijadas: `postgres:16.4`, `confluentinc/cp-kafka:7.7.1`,
`python:3.11.10-slim-bookworm` (base de productor, consumidor y API) y
`ngrok/ngrok:3.39.13-alpine` (túnel). Las dependencias de Python están fijadas con todas sus
transitivas en el `requirements.txt` de cada servicio.

## 4. Puesta en marcha

### Crear `.env`

```bash
cp .env.example .env
```

Editar `.env` y sustituir cada `CHANGE_ME_LOCALLY` por una contraseña local: `POSTGRES_PASSWORD`
(propietario de la base), `DB_WRITER_PASSWORD` (productor y consumidor) y `DB_READER_PASSWORD`
(API). Poner en `CORS_ORIGINS` el origen exacto del sitio de Netlify. `.env` está en
`.gitignore`: no se versiona nunca. La lista completa de variables está en
[contracts/runtime.md](specs/002-platform-data-model/contracts/runtime.md) y, para la ingesta,
en [contracts/runtime.md de la spec 003](specs/003-usgs-ingestion/contracts/runtime.md).

### Arrancar

```bash
docker compose up --build -d
```

La primera vez la base se crea sola desde `db/sql/` (esquemas, roles, dimensiones con los 177
países y los días de 1900 a 2035, tablas de eventos y privilegios). No hay pasos manuales.

### Comprobar el estado y los logs

```bash
docker compose ps
curl -s http://127.0.0.1:8000/api/salud
docker compose logs -f producer consumer
```

Los cinco servicios deben aparecer como `healthy` en menos de tres minutos con las imágenes ya
construidas. La salud del productor y del consumidor se basa en un latido; la de la API, en
`GET /api/salud`, que responde `degraded` si la base no está disponible. El productor actualiza
el latido tras cada consulta a USGS que queda registrada, **también si USGS falla**: un fallo de
la fuente no es un fallo del servicio y se ve en la antigüedad de la última ingesta. El productor
deja de estar sano si no puede registrar las consultas (base caída) o Kafka rechaza los
mensajes durante más de tres intervalos. Si una dependencia cae, los servicios reintentan con
espera exponencial de 1 s a 30 s y se recuperan sin reiniciarlos.

Cada consulta al feed queda en `core.extraction`. Para ver la última ingesta correcta, abrir
`psql` como se indica a continuación y ejecutar:

```sql
SELECT max(requested_at) FROM core.extraction
WHERE source = 'usgs_feed' AND outcome IN ('ok', 'not_modified');
```

Para consultar la base:

```bash
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

### Parar

```bash
docker compose down
```

Se conservan los volúmenes `postgres_data` (eventos, versiones, cuarentena y estado de
publicación) y `kafka_data` (mensajes durante 7 días y offsets confirmados). Al volver a
arrancar, el productor no republica versiones ya publicadas y el consumidor sigue donde lo dejó.

### Recrear la base desde cero

Los ficheros de inicialización solo se ejecutan con el volumen vacío. Para aplicar un cambio
del modelo, o si el volumen viene de una versión anterior, hay que borrar los volúmenes.
**Esto elimina todos los datos locales**:

```bash
docker compose down -v
docker compose up -d
```

## 5. Túnel para el panel publicado

Con `NGROK_AUTHTOKEN` y `NGROK_DOMAIN` (dominio reservado) en `.env`:

```bash
docker compose --profile tunnel up -d
docker compose --profile tunnel logs tunnel
curl -s "https://TU-DOMINIO.ngrok-free.app/api/salud" -H "ngrok-skip-browser-warning: 1"
```

El túnel apunta a `http://api:8000` dentro de la red de Compose. Para retirarlo:

```bash
docker compose --profile tunnel stop tunnel
```

Sin `--profile tunnel` el servicio no arranca, y los cinco obligatorios funcionan igual.

## 6. API

Base: `http://127.0.0.1:8000/api` (o la URL del túnel).

```bash
curl "http://127.0.0.1:8000/api/eventos?format=geojson&min_mag=4"
curl "http://127.0.0.1:8000/api/estadisticas/paises"
curl "http://127.0.0.1:8000/api/estadisticas/timeline?bucket=month"
```

`/eventos` acepta `country`, `country_id`, `start`, `end`, `date_from`, `date_to`, `min_mag`,
`min_magnitude`, `max_magnitude`, `limit` y `offset`. También están `/salud` y
`/estadisticas`. Con `format=geojson` o `Accept: application/geo+json` devuelve un
`FeatureCollection`. La magnitud, la profundidad y el país pueden ser nulos. Los rangos
incompatibles devuelven HTTP 400 y la base no disponible, HTTP 503 sin detalles internos. CORS
admite solo los orígenes de `CORS_ORIGINS` (sin comodín) y los métodos `GET` y `OPTIONS`.

El contrato definitivo de la API se rehace en la spec 006.

## 7. Datos

- `data/`: ubicación de los conjuntos descargados. Está fuera de Git; la carga del catálogo
  escribe en `data/usgs/catalog/` y el productor y el consumidor lo montan en solo lectura en
  `/data`. La base guarda la huella y la ruta de cada fichero (`core.raw_payload`).
- `db/seeds/`: lotes pequeños versionados para la reproducción, montados en `/seeds`. Ver
  [db/seeds/README.md](db/seeds/README.md).
- `frontend/public/datos/paises.geojson`: catálogo Natural Earth de 177 países, del que salen
  `core.dim_country` y el cruce espacial del consumidor.

Ninguna imagen contiene conjuntos de datos: se montan al ejecutar.

### Cargar el histórico

El histórico obligatorio (2025, mundial, magnitud ≥ 4, tipo terremoto) se carga a mano, una
vez, con el sistema arrancado:

```bash
docker compose run --rm catalog-loader
```

Tarda alrededor de un minuto con una conexión doméstica y deja unos 18.300 terremotos en el
esquema `core`. La orden divide el año en meses, pide primero a USGS cuántos eventos tiene cada
uno, divide el intervalo si supera el máximo de 20.000 y comprueba que cada descarga trae
exactamente lo declarado; nunca acepta una respuesta truncada. Al terminar muestra un resumen:

```text
Eventos distintos:      18302
Declarados por USGS:    18302   (recuento del periodo completo al terminar)
Diferencia:             0
```

| Código de salida | Significado |
|---|---|
| 0 | Carga completa, diferencia cero |
| 1 | Error (USGS no responde, Kafka o la base no están disponibles). Lo hecho se conserva: repetir la misma orden continúa |
| 2 | Argumentos no válidos; no se consulta USGS |
| 3 | Terminada, pero con diferencia frente al total de USGS; el resumen la detalla |

Repetir la orden no descarga de nuevo los meses ya completos ni publica nada dos veces. Para
actualizar la instantánea con las revisiones posteriores de USGS, añadir `--refresh`.

Otras opciones (ver [contracts/catalog-loader.md](specs/003-usgs-ingestion/contracts/catalog-loader.md)):

```bash
# Ampliación con 2026 hasta una fecha, con el mismo filtro
docker compose run --rm catalog-loader --start 2026-01-01 --end 2026-11-15

# Ver qué se descargaría, sin descargar ni publicar
docker compose run --rm catalog-loader --dry-run
```

Las respuestas se guardan sin modificar en `data/usgs/catalog/`, una por intervalo, con la huella
en el nombre (`2025-01-01T000000Z_2025-02-01T000000Z_m4_earthquake_<huella>.geojson`), y un
resumen `summary-*.json` por carga. Para comprobar que un fichero no ha cambiado:

```bash
(cd data && sha256sum usgs/catalog/*.geojson)
```

y comparar con `SELECT file_path, content_sha256 FROM core.raw_payload WHERE encoding = 'file'`.
Para regenerarlos desde cero basta con borrar `data/usgs/catalog/` y repetir la carga: un
intervalo cuyo fichero falta o no coincide con su huella se vuelve a descargar.

**En Linux**, la carga escribe en `./data` con el usuario indicado en `LOADER_UID` y
`LOADER_GID` (por defecto, `root`). Para que los ficheros sean tuyos:

```bash
LOADER_UID=$(id -u) LOADER_GID=$(id -g) docker compose run --rm catalog-loader
```

o escribir esos dos valores en `.env`. En Windows y macOS con Docker Desktop no hace falta.

### Paradas de más de 24 horas

El feed solo cubre las últimas 24 horas. Si el sistema ha estado parado más tiempo, al arrancar
el productor escribe en su log un aviso con el periodo perdido y la orden exacta para
recuperarlo, y sigue con el feed:

```bash
docker compose logs producer | grep "Ingestion gap detected"
docker compose run --rm catalog-loader --gaps      # huecos pendientes y recuperados
docker compose run --rm catalog-loader --purpose gap_recovery --start <inicio> --end <fin>
```

La recuperación trae todas las magnitudes del periodo, como el feed, y no duplica nada.

### Originales del feed

Cada respuesta distinta del feed se guarda comprimida en `core.raw_payload` y se borra cuando
lleva más de `RAW_PAYLOAD_RETENTION_DAYS` días (7) sin observarse. El productor purga al
arrancar y cada 24 horas; las consultas registradas no se borran nunca.

### Reproducción acelerada

```bash
docker compose run --rm producer python -m app.replay --path /seeds/historical_2025.jsonl --rate 10
```

Los mensajes van a `earthquakes.replay` y el consumidor los escribe en el esquema `replay`, que
no puede modificar los datos reales de `core`. En Git Bash, anteponer `MSYS_NO_PATHCONV=1` si la
ruta se convierte en una ruta de Windows. La reproducción completa se define en la spec 005.

## 8. Pruebas

Las pruebas se ejecutan en un contenedor dentro de la red de Compose, contra una base temporal
`observatory_test` que se crea con los mismos ficheros de `db/sql/` y se elimina al terminar:

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests pytest tests/db -v
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests pytest tests/unit tests/contract -v
```

`tests/db` cubre la secuencia de duplicados y revisiones de la FAQ 12, nulos y rangos,
idempotencia con 1.000 pasadas, privilegios, aislamiento de la reproducción y procedencia. Los
escenarios de validación con el sistema real están en
[specs/002-platform-data-model/quickstart.md](specs/002-platform-data-model/quickstart.md), y
sus resultados en [docs/evidence/002/](docs/evidence/002/).

## 9. Límites tecnológicos

El proyecto usa únicamente el stack aprobado: Python, Kafka, PostgreSQL, FastAPI, Docker
Compose, Angular y Leaflet. No usa PostGIS, Spark, Flink ni Kubernetes: el cruce espacial se
hace en Python con GeoPandas.
