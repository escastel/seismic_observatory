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

## 6. Consultar la API

Base: `http://127.0.0.1:8000/api` (o la URL del túnel del apartado 5, añadiendo la cabecera
`-H "ngrok-skip-browser-warning: 1"`). Solo acepta `GET` y `OPTIONS`; cualquier otro método
devuelve 405. Los tiempos son milisegundos Unix en UTC. Las fechas de entrada van en ISO 8601 con
zona horaria (`2025-01-01T00:00:00Z`); sin zona devuelven 422. Un desfase como `+02:00` debe
escribirse `%2B02:00` en la URL. El contrato completo está en
[specs/006-query-api/contracts/api.md](specs/006-query-api/contracts/api.md).

### Eventos

Sin parámetros devuelve las últimas 24 horas (ventana por defecto, `metadata.period.default_applied`
en `true`), todas las magnitudes y hasta 1.000 eventos:

```bash
curl "http://127.0.0.1:8000/api/eventos"
```

Con periodo, magnitud mínima y país. `start` es inclusivo y `end` exclusivo:

```bash
curl "http://127.0.0.1:8000/api/eventos?start=2025-01-01T00:00:00Z&end=2025-02-01T00:00:00Z&min_mag=4&country_id=ESP"
```

Si solo se indica `end`, la ventana por defecto son las 24 horas anteriores a él.

Paginación con `limit` (de 1 al máximo, 1.000 por defecto) y `offset` (0 o mayor). Para recorrer
todos los resultados, se pide una página, se lee `metadata.next_offset` y se repite con ese valor
como `offset`, con los mismos filtros, hasta que sea `null`. Si la primera página trajo 500
eventos, la siguiente empieza en `offset=500`:

```bash
curl "http://127.0.0.1:8000/api/eventos?start=2025-01-01T00:00:00Z&end=2025-02-01T00:00:00Z&limit=500&offset=0"
curl "http://127.0.0.1:8000/api/eventos?start=2025-01-01T00:00:00Z&end=2025-02-01T00:00:00Z&limit=500&offset=500"
```

### Estadísticas

Admiten los mismos filtros (`start`, `end`, `min_mag`, `country_id`) y `baseline_year` (2025 por
defecto), que fija el año de referencia de la comparación. Se calculan sobre el conjunto completo
del filtro, no sobre una página. Su `total` coincide con `metadata.total` de `/eventos` con los
mismos filtros; `comparison.ratio` vale `"ND"` si la media diaria de referencia es 0.

```bash
curl "http://127.0.0.1:8000/api/estadisticas?start=2025-01-01T00:00:00Z&end=2025-02-01T00:00:00Z&min_mag=4&country_id=ESP&baseline_year=2025"
curl "http://127.0.0.1:8000/api/estadisticas?min_mag=4&country_id=ESP"
```

La segunda orden, sin periodo, usa las últimas 24 horas, igual que `/eventos`.

### Salud

```bash
curl "http://127.0.0.1:8000/api/salud"
```

Responde siempre 200 con `status` `ok` o `degraded`. Con `degraded`, `database` o
`replay_database` valen `unavailable` y `last_ingestion` es `null`. No muestra credenciales ni
datos de conexión.

### Modo reproducción

Con `mode=replay` se consulta el esquema de reproducción en lugar de los datos reales, y no se
aplica la ventana de 24 horas por defecto. `exclude_synthetic=true` quita los casos sintéticos; solo
tiene efecto en este modo:

```bash
curl "http://127.0.0.1:8000/api/eventos?mode=replay&exclude_synthetic=true&limit=5"
curl "http://127.0.0.1:8000/api/estadisticas?mode=replay&exclude_synthetic=true"
```

En la respuesta, `metadata.mode` es `"replay"`, `metadata.label` es `"REPRODUCCIÓN"` y
`metadata.last_replayed_at` indica la última reproducción (milisegundos, o `null`). Cada `feature`
añade `properties.replayed_at` (milisegundos) y `properties.synthetic` (booleano).
`metadata.last_ingestion` sigue siendo la última consulta correcta a USGS. Ninguna respuesta
mezcla los dos esquemas.

### Errores

Todos los errores devuelven JSON. Con `curl -i` se ve el código de estado:

```bash
curl -i "http://127.0.0.1:8000/api/eventos?mode=x&start=2025-01-01T00:00:00"
```

Parámetro inválido, HTTP 422. Aquí `mode` no es `live` ni `replay`, y `start` no lleva zona horaria:

```json
{"error": "invalid_parameters", "detail": [{"param": "mode", "message": "..."}, {"param": "start", "message": "..."}]}
```

Base de datos no disponible, pool sin abrir o tiempo agotado, HTTP 503:

```json
{"error": "database_unavailable", "detail": "..."}
```

La API no devuelve `features: []` con 200 por un fallo. Un error inesperado devuelve 500 con
`{"error": "internal_error", "detail": "..."}`. Tras un 503, la API no necesita reiniciarse: en
cuanto la base vuelve, las consultas funcionan y `/salud` pasa a `ok`.

### Leer `metadata`

| Campo | Significado |
|---|---|
| `generated` | Instante en que se generó la respuesta (ms). |
| `last_ingestion` | Última consulta correcta a USGS (ms). Indica la frescura de los datos. |
| `mode` | `live` o `replay`. |
| `count` | Eventos en esta página. |
| `total` | Eventos que cumplen los filtros, en todas las páginas. |
| `limit`, `offset` | Página pedida. |
| `truncated` | `true` si `offset + count < total`: quedan eventos por pedir. |
| `next_offset` | `offset` de la página siguiente, o `null` si no quedan. |
| `period` | Periodo efectivo de la consulta; `default_applied: true` si se aplicó la ventana de 24 horas. |
| `null_magnitude` | Eventos con magnitud nula que cumplen el resto de filtros; `excluded: true` si hay `min_mag`, porque entonces no están en `features`. |
| `quarantined` | Filas de cuarentena no sintéticas del modo; `invalid_geometry` es el subconjunto por geometría. |

`generated` es cuándo respondió la API; `last_ingestion` es cuándo fue la última ingesta correcta.
Una respuesta recién generada con un `last_ingestion` antiguo significa que USGS no se ha consultado
con éxito desde hace tiempo. Para convertir un valor en fecha:

```bash
date -u -d @$((1793113140000/1000))
```

Los parámetros desconocidos se ignoran sin error. Por ejemplo, `format=geojson` no cambia nada: la
respuesta sigue siendo un `FeatureCollection`. Esto significa que un parámetro mal escrito produce
el resultado por defecto, no un aviso.

Ya no existen los nombres de la API anterior: `date_from`, `min_magnitude`, `country`, `format`,
`/estadisticas/paises`, `/estadisticas/timeline` y `/health`. Sus equivalentes son `start` y `end`,
`min_mag`, `country_id`, la respuesta `FeatureCollection` por defecto, `/estadisticas` y `/salud`.

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
docker compose run --rm replay start --start 2025-01-01 --end 2025-04-01 --min-mag 4.0 --rate 200
```

Los mensajes van a `earthquakes.replay` y el consumidor los escribe en el esquema `replay`, que
no puede modificar los datos reales de `core`. La selección sale de lo ya descargado en
`data/usgs/catalog/`; no se consulta a USGS. El procedimiento completo de la demostración de la
defensa (pausar, reanudar, detener, repetir y comprobar el aislamiento) está en
[Demostración de la defensa](#demostración-de-la-defensa).

### Demostración de la defensa

Sirve para enseñar el sistema con actividad aunque no ocurra ningún terremoto durante la defensa: se
reproduce a velocidad acelerada una selección del histórico ya descargado, por el mismo camino que los
datos reales (Kafka → consumidor → PostgreSQL), pero en el esquema `replay`, sin tocar `core`. No
consulta a USGS. Los datos reproducidos se reconocen desde la base por estar en el esquema `replay` y
tener `replayed_at`; el etiquetado «REPRODUCCIÓN» en la API y el panel llega con las specs 006 y 007.

**Requisitos**: el stack levantado y sano (`docker compose up --build -d`) y el catálogo de 2025 con
magnitud ≥ 4 descargado y registrado (`docker compose run --rm catalog-loader`, apartado
[Cargar el histórico](#cargar-el-histórico)). En Linux, antes de empezar:
`export LOADER_UID=$(id -u) LOADER_GID=$(id -g)` (la orden escribe sus ficheros de control en
`./data/replay/`). Todas las órdenes se lanzan desde la raíz del repositorio y no necesitan
`MSYS_NO_PATHCONV` en Git Bash.

En el texto, «terminal 1» y «terminal 2» son dos terminales abiertas en la raíz del repositorio.

**1. Ver la selección sin publicar** (terminal 1). Con enero a abril de 2025 y magnitud ≥ 4 salen
5.301 eventos:

```bash
docker compose run --rm replay select --start 2025-01-01 --end 2025-05-01 --min-mag 4.0
```

Anota el `extraction_id`: la selección queda registrada en `core.extraction` con propósito
`replay_selection`. Se rechaza, con código de salida 2, un periodo no descargado, una magnitud mínima
inferior a la del catálogo o un fichero alterado. Para limitar a una zona, `--bbox=` con
`min_lon,min_lat,max_lon,max_lat` (con el signo menos pegado: `--bbox=-125,32,-114,42`).

**2. Preparar la comprobación de aislamiento** (opcional, recomendada). El feed real escribe en `core`
por su cuenta, así que se para el productor mientras dura la comprobación y se toma una instantánea
(recuento y suma de comprobación de cada tabla de `core`):

```bash
docker compose stop producer
docker compose run --rm replay reset
docker compose run --rm replay snapshot
```

**3. Reproducir** (terminal 1). `--rate` son eventos por segundo; `--speedup 3600` añadiría un factor
sobre el tiempo original (con ambos, la cadencia nunca supera `--rate`). A 200 eventos/s, 5.301
eventos tardan unos 27 s; a 20 se alarga lo bastante para enseñar el control:

```bash
docker compose run --rm replay start --start 2025-01-01 --end 2025-05-01 --min-mag 4.0 --rate 20
```

**4. Controlarla** (terminal 2, mientras corre la 1). Solo puede haber una reproducción activa:

```bash
docker compose run --rm replay status    # estado, enviados, restantes
docker compose run --rm replay pause     # deja de publicar; el contador no avanza
docker compose run --rm replay resume    # sigue por el siguiente evento, sin saltos
docker compose run --rm replay stop      # termina; lo ya publicado se conserva
```

**5. Enseñar lo reproducido en la base** (cuando el consumidor esté al día):

```bash
docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT count(*), min(replayed_at), max(replayed_at) FROM replay.event_current"'
docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < docs/evidence/005/sql/v2-replayed-data.sql
```

La segunda consulta muestra que todo lo reproducido está en `replay`, que cada evento conserva su
tiempo de ocurrencia original (`event_time` sigue siendo de 2025; solo `replayed_at` es de hoy) y que
`core` no recibió nada del topic de reproducción.

**6. Comprobar que `core` no cambió** (con el productor parado, paso 2):

```bash
docker compose run --rm replay compare   # "core idéntico a la instantánea", código de salida 0
```

**7. Repetir desde cero**: `reset` vacía solo las tablas de `replay` (no existe operación equivalente
en `core`), y se vuelve a lanzar el paso 3. El resultado es idéntico al de la primera vez.

```bash
docker compose run --rm replay reset
```

**8. Casos sintéticos** (primera versión, repetición exacta, revisión, versión antigua tardía y un
mensaje a cuarentena; 7 mensajes con resultado conocido):

```bash
docker compose run --rm replay reset
docker compose run --rm replay start --synthetic-only
docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < docs/evidence/005/sql/v6-synthetic-cases.sql
```

Esperado: `new` 3, `duplicate` 1, `revised` 1, `stale` 1 y `quarantined` 1. Con `--synthetic` en lugar de
`--synthetic-only`, los siete mensajes se añaden al final de una selección real.

**9. Al terminar**: `docker compose start producer` para reanudar la ingesta real.

Notas:

- El consumidor puede reiniciarse a mitad de la reproducción (`docker compose restart consumer`): al
  terminar, el resultado es el mismo que sin reinicio.
- Si se crea un consumidor con un grupo nuevo, empieza por el principio del topic de reproducción
  (retención de 168 h) y repuebla `replay` con reproducciones anteriores; no afecta a `core`.
- Procedimiento detallado y evidencia de cada escenario en
  [specs/005-historical-replay/quickstart.md](specs/005-historical-replay/quickstart.md) y
  [docs/evidence/005/](docs/evidence/005/README.md); explicación y resultados medidos en
  [docs/report.md](docs/report.md#reproducción-histórica).

### Calidad de los datos

El consumidor aplica reglas explícitas, cada una con un código estable
([catálogo de reglas](specs/004-consumer-quality/contracts/rules-catalog.md)). Solo va a
cuarentena lo que no puede tratarse (JSON ilegible, sin identificador, tiempo o versión,
geometría que no es un punto, coordenadas imposibles, o una versión que el modelo rechaza), con
**todos** los motivos y el mensaje original. La magnitud, la profundidad y el tipo de magnitud
ausentes se guardan nulos, nunca como cero; las anomalías (profundidad negativa, valores fuera
de rango, tiempo futuro…) se señalan en `quality_flags` sin rechazar el evento. El país se
obtiene por punto en polígono; sin polígono queda nulo («Sin país asignado»).

Los recuentos de cada regla se obtienen de lo almacenado, con el denominador explícito:

```bash
docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /queries/quality.sql'
```

El análisis completo, por dimensión, está en el apartado «Calidad de los datos» de
[docs/report.md](docs/report.md).

**Reprocesar la cuarentena** con las reglas vigentes (por ejemplo, tras retirar una regla):

```bash
docker compose run --rm quality-reprocess --dry-run     # solo lista lo que haría
docker compose run --rm quality-reprocess
```

Es idempotente y no borra nada: cada fila de cuarentena queda marcada con la fecha y el
resultado (`recovered_*` o `still_rejected`), y el registro de mensajes conserva el resultado
original junto al del reprocesado.

**Casos de prueba dañados a propósito.** Se inyectan en el sistema real, separados de los datos
reales (prefijo `synthetic-` y marca `synthetic`), que las consultas de calidad excluyen:

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm \
  -e KAFKA_BOOTSTRAP_SERVERS=kafka:9092 -e KAFKA_TOPIC_LIVE=earthquakes.live \
  -e KAFKA_TOPIC_CATALOG=earthquakes.catalog -e KAFKA_TOPIC_REPLAY=earthquakes.replay \
  tests python -m tests.synthetic.inject --list      # sin --list los publica; repetirlo no duplica nada
```

**Base creada antes de la spec 004.** Los ficheros de `db/sql/` solo se ejecutan con el volumen
vacío. Para añadir a una base existente las columnas de reprocesado sin recrearla:

```bash
MSYS_NO_PATHCONV=1 docker compose exec -T postgres sh -c \
  'export PGUSER="$POSTGRES_USER"; /sql/apply.sh "$POSTGRES_DB" 041_consumer_quality.sql'
```

## 8. Pruebas

Las pruebas se ejecutan en un contenedor dentro de la red de Compose, contra una base temporal
`observatory_test` que se crea con los mismos ficheros de `db/sql/` y se elimina al terminar:

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests pytest tests/db -v
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests pytest tests/unit tests/contract -v
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests pytest tests/unit/test_replay_*.py -v
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
