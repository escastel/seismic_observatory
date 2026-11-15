# Memoria del Observatorio Sísmico

Este documento reúne las decisiones de diseño del observatorio y su justificación. Se completa
funcionalidad a funcionalidad; esta versión contiene los apartados de la plataforma y el modelo
de datos (spec 002). Las cifras citadas proceden de mediciones guardadas en
[docs/evidence/002/](evidence/002/).

## Alcance y decisiones

**Datos que el sistema debe guardar.** El enunciado exige el histórico mundial de 2025 con
magnitud ≥ 4 y tipo terremoto (unos 16.000 eventos) y el feed en vivo de USGS de las últimas
24 horas, consultado cada minuto (unos 200 eventos nuevos y hasta 10.080 consultas por semana).
El histórico de 2025 es dato real: se guarda en el esquema `core`, distinguido del feed por su
procedencia (`source = 'usgs_catalog'`), y no en el de reproducción. El modelo no impide cargar
el catálogo completo desde 1900: la dimensión de fecha empieza ese año y las tablas no tienen
límites de volumen; la carga ampliada queda para una funcionalidad posterior.

**Decisiones propias del modelo.**

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Esquemas `core` (real) y `replay` (reproducción) con la misma plantilla de tablas | Una columna «origen» en tablas compartidas | El aislamiento queda garantizado por la estructura: una consulta o un borrado de `replay` no puede tocar `core` |
| Regla de versiones en la función `apply_event_version` | Dos sentencias desde Python | La regla vive junto a sus restricciones, se prueba con SQL y devuelve el resultado que se cuenta (`new`, `revised`, `stale`, `duplicate`) |
| País nulo cuando el punto no cae en ningún polígono | Fila ficticia «Sin país asignado» | No se inventa una entidad en la dimensión; el texto lo pone la presentación |
| Magnitud y profundidad anulables, sin mínimo | Rechazar nulos y negativos | El principio III obliga a conservar o señalar; una magnitud negativa o una profundidad sobre el nivel del mar son reales |
| Tres roles de base de datos (propietario, escritor, lector) | Un único usuario | La API, única pieza expuesta a Internet, no puede modificar datos aunque tenga un fallo |
| Registro de cada mensaje procesado (`message_log`) | Contar en los logs | Da los denominadores de calidad con SQL; no es fuente de recuentos de terremotos |
| Originales del feed comprimidos, una vez por huella y durante 7 días | Guardar todos los cuerpos sin límite | Con hasta 10.080 consultas por semana, 30 días superarían 1,5 GB; 7 días quedan por debajo de 400 MB |
| Índices secundarios solo si su consulta es al menos 2 veces más rápida | Indexar todo de antemano | Cada índice cuesta espacio y escrituras; se conserva el que demuestra su beneficio |

**Material reutilizado frente a desarrollado.**

| Reutilizado | Desarrollado en este proyecto |
|---|---|
| Catálogo de países Natural Earth entregado (`frontend/public/datos/paises.geojson`, 177 entidades) | Modelo de datos completo (`db/sql/`), función de versiones, reglas de esquema y privilegios |
| Imágenes oficiales de PostgreSQL 16.4, Kafka 7.7.1 (Confluent), Python 3.11 y ngrok | `compose.yaml`, comprobaciones de salud, reintentos y creación de topics (`common/`) |
| Bibliotecas: aiokafka, asyncpg, FastAPI, GeoPandas, Shapely | Pruebas del modelo (`tests/db`), medición de índices (`tests/benchmark`) y arranques (`tests/startup`) |
| Feed y API de catálogo de USGS como fuente de datos | Adaptación de productor, consumidor y API al modelo nuevo |

## Modelo conceptual

```mermaid
erDiagram
    COUNTRY ||--o{ EVENT_CURRENT : "contiene (opcional)"
    DATE ||--o{ EVENT_CURRENT : "ocurre en"
    EVENT_CURRENT ||--|{ EVENT_VERSION : "tiene versiones"
    EXTRACTION }o--o| RAW_PAYLOAD : "obtuvo"
    EXTRACTION ||--o{ EXCLUDED_EVENT : "descartó"
    PUBLISH_STATE ||--o| EVENT_CURRENT : "mismo identificador"
    QUARANTINE }o--o| EVENT_CURRENT : "puede referirse a"
    MESSAGE_LOG }o--o| EVENT_VERSION : "trajo"
```

- Un **terremoto** es la versión más reciente conocida de un evento de USGS y tiene **una o más
  versiones**, una por cada `updated` distinto.
- Un terremoto ocurre en **un día UTC** y, si su punto cae dentro de un polígono del catálogo,
  en **un país**.
- Una **extracción** es una consulta a USGS: puede haber guardado un **original** y haber
  descartado elementos que no son terremotos.
- El **estado de publicación** recuerda qué versión de cada evento envió el productor a Kafka.
- La **cuarentena** guarda los mensajes que no se pudieron tratar, con el original.
- El **registro de mensajes** anota cada mensaje procesado y su resultado.

## Modelo lógico

### Grano y claves

| Esquema | Tabla | Una fila representa | Clave |
|---|---|---|---|
| `core` | `dim_country` | Una entidad del catálogo Natural Earth | `country_id` |
| `core` | `dim_date` | Un día UTC | `date_id` |
| `core` | `extraction` | Una consulta a USGS | `extraction_id` |
| `core` | `raw_payload` | Un contenido original distinto | `content_sha256` |
| `core`, `replay` | `event_current` | La versión más reciente de un terremoto | `event_id` |
| `core`, `replay` | `event_version` | Una versión observada de un terremoto | `(event_id, updated_at)` |
| `core`, `replay` | `quarantine` | Un mensaje rechazado | `quarantine_id`; única `(kafka_topic, kafka_partition, kafka_offset)` |
| `core`, `replay` | `excluded_event` | Una versión de un elemento que no es un terremoto | `(event_id, updated_at)` |
| `core`, `replay` | `publish_state` | La última versión publicada de un evento | `event_id` |
| `core`, `replay` | `message_log` | Un mensaje procesado por el consumidor | `(kafka_topic, kafka_partition, kafka_offset)` |

`replay` usa las dimensiones de `core`. Durante la medición de índices existe además un esquema
`bench` con la misma plantilla, que se elimina al terminar.

### Relaciones

- `event_current.country_id` → `core.dim_country` (opcional: nulo = sin país).
- `event_current.event_date` → `core.dim_date` (obligatoria; columna generada desde `event_time`).
- `event_version.event_id` → `event_current.event_id` del mismo esquema, con borrado en cascada.
- `excluded_event.extraction_id` → `core.extraction` (opcional), también desde `replay`.
- Sin clave foránea, a propósito: `message_log` (un rechazo no corresponde a ninguna versión),
  `extraction.content_sha256` (la extracción sobrevive a la purga del original), `publish_state`
  y `quarantine` (un evento puede estar publicado y aún no consumido, o no existir nunca como
  válido).

### Regla de versiones

| Situación al llegar una versión | Estado actual | Historial | Resultado |
|---|---|---|---|
| Identificador desconocido | Se crea | Se añade | `new` |
| `updated_at` posterior al guardado | Se sustituye por completo | Se añade | `revised` |
| `updated_at` igual a uno ya visto | Sin cambios | Sin cambios | `duplicate` |
| `updated_at` anterior y nunca visto | Sin cambios | Se añade | `stale` |

La secuencia de la FAQ 12 (E1 a las 10:05 con 4,2; repetición; E1 a las 10:09 con 4,6; E1 a las
10:05 otra vez; E2 a las 10:12 con 3,1) da `new`, `duplicate`, `revised`, `duplicate`, `new`: 2
terremotos, 3 versiones y 5 mensajes registrados. Reprocesar 1.000 veces 50 mensajes deja los
mismos recuentos que la primera pasada ([db-tests.txt](evidence/002/db-tests.txt)).

## Modelo físico

El modelo se define en un único conjunto ordenado de ficheros SQL, aplicado por
[db/sql/apply.sh](../db/sql/apply.sh) al crear el volumen (y por las pruebas a una base
temporal):

| Fichero | Contenido |
|---|---|
| [010_roles_schemas.sql](../db/sql/010_roles_schemas.sql) | Esquemas `core` y `replay`; roles `observatory_writer` y `observatory_reader` |
| [020_dimensions.sql](../db/sql/020_dimensions.sql) | `dim_country`, cargada desde el GeoJSON con `pg_read_file`, y `dim_date` de 1900 a 2035 |
| [030_extraction.sql](../db/sql/030_extraction.sql) | `extraction`, `raw_payload` y `purge_raw_payload` |
| [040_event_tables.sql](../db/sql/040_event_tables.sql) | Plantilla por esquema: tablas de eventos y `apply_event_version` |
| [050_schema_rules.sql](../db/sql/050_schema_rules.sql) | Reglas de `replayed_at` en cada esquema y `replay.reset()` |
| [060_indexes.sql](../db/sql/060_indexes.sql) | Plantilla por esquema: índices secundarios que superaron la medición |
| [070_grants.sql](../db/sql/070_grants.sql) | Privilegios mínimos de los dos roles |

Restricciones principales: longitud en [−180, 180] y latitud en [−90, 90]; magnitud,
profundidad y coordenadas finitas (ni NaN ni infinito); `source`, `purpose`, `outcome` y
`encoding` dentro de sus valores; `replayed_at` nulo en `core` y obligatorio en `replay`;
cuarentena con al menos un motivo y con el original (JSON o texto); `raw_payload` con cuerpo o
ruta de fichero.

Tipos: `timestamptz` para todos los instantes (UTC); `double precision` para magnitud,
coordenadas y profundidad, que USGS publica como números de coma flotante; `text` con `CHECK`
para los valores cerrados, más fáciles de ampliar que un tipo enumerado; `jsonb` para los
originales; `text[]` para motivos y señales de calidad.

## Diccionario de datos

Convenciones: los instantes son `timestamptz` y se interpretan en UTC; «Ausencias» indica qué
se guarda cuando el dato no llega. Las tablas de eventos son idénticas en `core` y `replay`.

### `core.dim_country`

Origen: `frontend/public/datos/paises.geojson` (Natural Earth Admin 0), cargado una vez. 177 filas.

| Columna | Tipo | Significado y origen | Ausencias |
|---|---|---|---|
| `country_id` | `text`, clave | `ADM0_A3` de Natural Earth; no es necesariamente un código ISO | Nunca falta |
| `name_es` | `text` | `NAME_ES`, nombre mostrado en el panel | Nunca falta |
| `admin_name` | `text` | `ADMIN`, nombre administrativo en inglés | Nunca falta |
| `continent` | `text` | `CONTINENT` | Nunca falta |
| `subregion` | `text` | `SUBREGION` | Nunca falta |
| `iso_a3` | `text` | `ISO_A3`, informativo | `-99` en el catálogo se guarda como nulo (5 entidades: Noruega, Francia, Chipre del Norte, Somalilandia y Kosovo) |

### `core.dim_date`

Un día UTC por fila, de 1900-01-01 a 2035-12-31 sin huecos (49.673 filas), para poder contar
días sin eventos.

| Columna | Tipo | Significado | Ausencias |
|---|---|---|---|
| `date_id` | `date`, clave | Día UTC | — |
| `year`, `quarter`, `month`, `day` | `smallint` | Año, trimestre (1–4), mes (1–12) y día del mes | — |
| `iso_week` | `smallint` | Semana ISO 8601 (1–53) | — |
| `iso_dow` | `smallint` | Día de la semana ISO (1 = lunes, 7 = domingo) | — |
| `day_of_year` | `smallint` | Día del año (1–366) | — |

### `core.extraction`

Una fila por consulta a USGS (feed o catálogo), conservada indefinidamente.

| Columna | Tipo | Significado y unidad | Ausencias |
|---|---|---|---|
| `extraction_id` | `bigint` identidad, clave | Identificador interno | — |
| `source` | `text` | `usgs_feed` o `usgs_catalog` | — |
| `purpose` | `text` | `live`, `historical_load`, `gap_recovery` o `replay_selection` | — |
| `request_url` | `text` | URL completa consultada | — |
| `request_params` | `jsonb` | Parámetros del catálogo (intervalo, magnitud mínima, tipo) | Nulo en el feed |
| `window_start`, `window_end` | `timestamptz` | Intervalo pedido al catálogo; el final es posterior al inicio | Nulo en el feed |
| `requested_at` | `timestamptz` | Inicio de la consulta | — |
| `duration_ms` | `integer`, ms | Latencia total, reintentos incluidos | Nulo si no se midió |
| `attempt_count` | `smallint` | Intentos realizados (≥ 1) | 1 por defecto |
| `http_status` | `integer` | Último código HTTP | Nulo si no hubo respuesta (tiempo agotado) |
| `outcome` | `text` | `ok`, `not_modified`, `http_error`, `timeout`, `invalid_json` o `invalid_structure` | — |
| `error_detail` | `text` | Descripción del fallo | Nulo si fue correcta |
| `source_generated_at` | `timestamptz` | `metadata.generated` de la respuesta (ms Unix convertidos a UTC) | Nulo si no hubo cuerpo válido |
| `record_count` | `integer` | Elementos recibidos | Nulo si no hubo cuerpo válido |
| `earthquake_count`, `excluded_count`, `published_count` | `integer` | Reparto de los elementos: terremotos, excluidos por tipo y versiones publicadas | Nulo si no hubo cuerpo válido |
| `content_sha256` | `text` | Huella SHA-256 de la colección de eventos (no de la cabecera, que cambia en cada respuesta) | Nulo si no hubo cuerpo válido |

### `core.raw_payload`

Una fila por contenido original distinto.

| Columna | Tipo | Significado y unidad | Ausencias |
|---|---|---|---|
| `content_sha256` | `text`, clave | Huella del contenido | — |
| `encoding` | `text` | `gzip` (cuerpo del feed en la base) o `file` (fichero en `data/`) | — |
| `body` | `bytea` | Cuerpo comprimido con gzip | Nulo para ficheros; se purga a los 7 días (`RAW_PAYLOAD_RETENTION_DAYS`) |
| `file_path` | `text` | Ruta bajo `data/` del fichero del catálogo | Nulo para cuerpos del feed |
| `byte_size` | `integer`, bytes | Tamaño sin comprimir | — |
| `first_seen_at`, `last_seen_at` | `timestamptz` | Primera y última vez que se obtuvo este contenido | — |

### `core.event_current`, `replay.event_current`

Una fila por terremoto: su versión más reciente.

| Columna | Tipo | Significado, unidad y conversión | Ausencias |
|---|---|---|---|
| `event_id` | `text`, clave | `id` de USGS | Sin él, el mensaje va a cuarentena |
| `source` | `text` | `usgs_feed` (feed en vivo) o `usgs_catalog` (catálogo histórico) | — |
| `event_time` | `timestamptz` | Ocurrencia: `properties.time`, ms Unix convertidos a UTC | Sin él, cuarentena |
| `event_date` | `date`, generada | Día UTC de `event_time`; clave foránea a `dim_date`; se recalcula si una revisión cambia `event_time` | — |
| `updated_at` | `timestamptz` | Versión en USGS: `properties.updated`, ms Unix convertidos a UTC | Sin él, cuarentena |
| `magnitude` | `double precision`, adimensional | `properties.mag`; su escala depende de `mag_type`; sin mínimo (hay magnitudes negativas) | Se guarda nulo; el panel muestra «ND» |
| `mag_type` | `text` | `properties.magType` (ml, mb, mw, md…) | Nulo |
| `longitude` | `double precision`, grados WGS84 | `geometry.coordinates[0]`, en [−180, 180] | Inválida: cuarentena |
| `latitude` | `double precision`, grados WGS84 | `geometry.coordinates[1]`, en [−90, 90] | Inválida: cuarentena |
| `depth_km` | `double precision`, km | `geometry.coordinates[2]`; negativa si el foco está sobre el nivel del mar | Se guarda nulo; el panel muestra «ND» |
| `place` | `text` | `properties.place`, descripción libre | Nulo |
| `country_id` | `text` | Entidad de `dim_country` que contiene el punto (punto en polígono en el consumidor) | Nulo = «Sin país asignado» (mar o fuera de todo polígono) |
| `quality_flags` | `text[]` | Anomalías señaladas sin rechazar el evento (p. ej. `negative_depth`) | Lista vacía |
| `first_ingested_at` | `timestamptz` | Primera vez que el consumidor guardó el evento; no cambia en las revisiones | — |
| `ingested_at` | `timestamptz` | Última escritura del consumidor (tiempo de procesamiento) | — |
| `replayed_at` | `timestamptz` | Instante de reproducción; el `event_time` original no se modifica | Siempre nulo en `core`; obligatorio en `replay` |

### `core.event_version`, `replay.event_version`

Una fila por versión observada.

| Columna | Tipo | Significado | Ausencias |
|---|---|---|---|
| `event_id` | `text` | Evento al que pertenece; clave foránea a `event_current` | — |
| `updated_at` | `timestamptz` | Identidad de la versión; clave junto con `event_id` | — |
| `source` | `text` | Procedencia de esta versión | — |
| `event_time` | `timestamptz` | Ocurrencia según esta versión | — |
| `magnitude`, `mag_type`, `depth_km` | como en `event_current` | Valores de esta versión, para ver los cambios sin abrir el original | Nulos como en `event_current` |
| `longitude`, `latitude` | `double precision`, grados | Posición según esta versión | — |
| `payload` | `jsonb` | `Feature` original de USGS, sin transformar | — |
| `received_at` | `timestamptz` | Momento en que el consumidor recibió la versión por primera vez | — |
| `kafka_topic`, `kafka_partition`, `kafka_offset` | `text`, `integer`, `bigint` | Mensaje que trajo la versión por primera vez; una repetición no lo cambia | — |

### `core.publish_state`, `replay.publish_state`

| Columna | Tipo | Significado | Ausencias |
|---|---|---|---|
| `event_id` | `text`, clave | Evento | — |
| `updated_at` | `timestamptz` | Última versión confirmada por Kafka; nunca retrocede | — |
| `published_at` | `timestamptz` | Momento de esa confirmación | — |

### `core.quarantine`, `replay.quarantine`

Una fila por mensaje rechazado; reprocesarlo no crea otra.

| Columna | Tipo | Significado | Ausencias |
|---|---|---|---|
| `quarantine_id` | `bigint` identidad, clave | Identificador interno | — |
| `kafka_topic`, `kafka_partition`, `kafka_offset` | `text`, `integer`, `bigint` | Posición del mensaje; única en conjunto | — |
| `event_id` | `text` | Identificador, si se pudo leer | Nulo |
| `reason_codes` | `text[]` | Todos los códigos de motivo encontrados (al menos uno) | — |
| `reason_detail` | `text` | Explicación legible, con la dimensión de calidad de cada motivo | — |
| `payload` | `jsonb` | Mensaje original, si es JSON | Nulo si no lo es |
| `raw_text` | `text` | Mensaje original como texto, si no es JSON | Nulo si es JSON; nunca faltan los dos |
| `is_synthetic` | `boolean` | Caso dañado a propósito para pruebas | `false` |
| `quarantined_at` | `timestamptz` | Momento del rechazo | — |

### `core.excluded_event`, `replay.excluded_event`

Versiones de elementos de USGS que no son terremotos (voladuras, explosiones…).

| Columna | Tipo | Significado | Ausencias |
|---|---|---|---|
| `event_id`, `updated_at` | `text`, `timestamptz` | Identidad de la versión excluida; clave | — |
| `event_type` | `text` | `properties.type` recibido (`quarry blast`, `explosion`…) | Nulo si no venía |
| `reason_code` | `text` | Motivo de la exclusión | `not_earthquake` por defecto |
| `extraction_id` | `bigint` | Extracción en la que se vio por primera vez; clave foránea a `core.extraction` | Nulo |
| `payload` | `jsonb` | `Feature` original | — |
| `first_seen_at` | `timestamptz` | Primera observación | — |

### `core.message_log`, `replay.message_log`

Una fila por mensaje de Kafka procesado. Es una auditoría de la ingesta, no una fuente de
recuentos de terremotos.

| Columna | Tipo | Significado | Ausencias |
|---|---|---|---|
| `kafka_topic`, `kafka_partition`, `kafka_offset` | `text`, `integer`, `bigint` | Posición del mensaje; clave conjunta | — |
| `event_id` | `text` | Evento al que se refiere | Nulo si no se pudo leer |
| `updated_at` | `timestamptz` | Versión a la que se refiere | Nulo en los rechazos |
| `outcome` | `text` | `new`, `revised`, `stale`, `duplicate` o `quarantined` | — |
| `produced_at` | `timestamptz` | `ingested_at` del mensaje: cuándo lo obtuvo el productor | Nulo si el mensaje no lo trae |
| `processed_at` | `timestamptz` | Cuándo lo procesó el consumidor | — |

Denominadores que permite: mensajes recibidos (filas), versiones distintas (`event_version`),
terremotos actuales (`event_current`), repeticiones (`outcome = 'duplicate'`) y rechazos
(`outcome = 'quarantined'`). `processed_at − produced_at` mide el retraso del transporte.

## Índices

Solo las claves primarias y las restricciones únicas se crearon de antemano. Cada índice
secundario candidato (research.md R11) se midió con datos sintéticos de 10.000, 100.000 y
1.000.000 de eventos en un esquema `bench` con la misma plantilla, y se conserva si su consulta
es al menos 2 veces más rápida en mediana con 1.000.000 de filas (FR-027). Procedimiento
completo, equipo y todas las cifras: [index-benchmark.md](evidence/002/index-benchmark.md),
generado por [tests/benchmark/index_benchmark.py](../tests/benchmark/index_benchmark.py).
Equipo: Windows 11 con Docker Desktop (12 CPU y 7,6 GiB para el motor), PostgreSQL 16.4 con la
configuración por defecto (`shared_buffers` 128 MB), 2026-11-15.

### Índices conservados

Mediana de 5 ejecuciones con `EXPLAIN (ANALYZE, BUFFERS)`, en milisegundos, y búferes leídos
con 1.000.000 de filas:

| Índice | Consulta que resuelve | Sin índice | Con índice | Mejora | Tamaño |
|---|---|---:|---:|---:|---:|
| `event_current (event_time)` | Últimas 24 h del mapa | 53,6 ms · 20.073 búferes | 0,43 ms · 76 | ×126 | 21,5 MiB |
| ídem | Un mes agrupado por hora UTC | 51,3 ms · 20.071 | 21,8 ms · 228 | ×2,4 | ídem |
| `event_current (country_id, event_time)` | Un país en un mes | 55,1 ms · 20.073 | 0,28 ms · 324 | ×199 | 30,1 MiB |
| `event_current (magnitude, event_time)` | Magnitud ≥ 4 en un año | 40,4 ms · 20.073 | 1,00 ms · 988 | ×40 | 30,1 MiB |
| `core.extraction (requested_at)` parcial, solo feed correcto | `last_ingestion` | 79,0 ms · 19.608 | 0,016 ms · 4 | ×4.936 | 19,8 MiB |
| Clave primaria `event_version (event_id, updated_at)` | Versiones de un evento | 68,0 ms · 61.824 (copia sin clave) | 0,014 ms · 4 | ×4.859 | 70,6 MiB |

Los cuatro índices secundarios están en [060_indexes.sql](../db/sql/060_indexes.sql), cada uno
con un comentario que cita su consulta y su medición. Se crean en `core` y en `replay`; el de
`extraction`, solo en `core`, que es donde existe la tabla.

Matices de la medición:

- La mejora del índice de magnitud depende de la selectividad. Con la distribución de
  Gutenberg-Richter usada (b = 1 desde M1), M ≥ 4 es el 0,1 % de los eventos, como en el feed
  mundial completo. En el histórico de 2025, que solo contiene M ≥ 4, el filtro `min_mag=4` no
  selecciona nada y el planificador recorrerá la tabla o usará el índice de tiempo; el índice
  sigue sirviendo para umbrales más altos.
- La agrupación por hora de un mes es la consulta con menos margen (×2,4): un mes es el 8 % del
  año, y una vez localizadas las filas hay que agruparlas todas. El índice permite un recorrido
  solo de índice (228 búferes frente a 20.071).

### Índices descartados o solo medidos

| Candidato | Resultado con 1.000.000 de filas | Decisión |
|---|---|---|
| BRIN sobre `event_current (event_time)` | Últimas 24 h ×34 (1,56 ms) y un mes por hora ×2,0 (25,6 ms); ocupa 0,02 MiB | No se crea: R11 lo prevé solo como medición, y el B-tree es más rápido en las dos consultas (×126 y ×2,4). Es la alternativa si el espacio pasara a ser el límite |
| Índice aparte sobre `event_version (event_id)` | — | No se crea: la clave primaria ya empieza por `event_id`. El modelo anterior tenía este índice duplicado (`ix_event_versions_external_id`) |

### Razonamiento para 100 millones de registros

Las mediciones muestran la tendencia que importa. Sin índice, el tiempo crece en proporción a
las filas: unos 0,5 ms con 10.000, unos 5 ms con 100.000 y unos 50 ms con 1.000.000 en las
cuatro consultas sobre `event_current`, porque cada una lee toda la tabla (200, 2.000 y 20.000
búferes). Extrapolando, con 100 millones de filas serían unos 5 s por consulta y unos 2 millones
de búferes (16 GB) leídos, muy por encima de la memoria del equipo: la tabla dejaría de caber en
caché y el tiempo lo marcaría el disco.

Con índice, el coste depende de las filas que devuelve la consulta, no del tamaño de la tabla:
las últimas 24 h pasan de 0,013 a 0,06 y 0,43 ms al multiplicar la tabla por 10 y por 100,
porque esas 24 h contienen 10 y 100 veces más eventos en los datos sintéticos (uniformes en un
año). Con 100 millones de terremotos repartidos en muchos años, un día tendría un volumen real,
y la profundidad de un B-tree solo crece en uno o dos niveles. A esa escala harían falta además:

- **Particionar `event_current` y `event_version` por rango de `event_time`** (por año), para
  que las consultas por intervalo descarten particiones enteras y el mantenimiento (`VACUUM`,
  reindexado) trabaje por partes. La clave primaria tendría que incluir la clave de partición.
- **Revisar el BRIN**: con datos insertados en orden temporal, su tamaño (0,02 MiB frente a
  21 MiB con 1.000.000 de filas) lo convierte en la opción para las particiones antiguas, que
  apenas se escriben.
- **Agregados precalculados por día y país**, alimentados desde `event_current`, para los
  gráficos que recorren todo el histórico. Mantienen el principio VII si se recalculan desde el
  estado actual y no se incrementan con contadores.
- **Más memoria para PostgreSQL** (`shared_buffers`, `work_mem`) que los valores por defecto
  usados aquí.

Nada de esto hace falta para el volumen del proyecto (unos 16.000 eventos del histórico obligatorio
más el feed), donde las cuatro consultas tardan menos de un milisegundo con índice.
