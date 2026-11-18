# Data Model: Ingesta desde USGS

**Fecha**: 2026-11-15 · **Spec**: `spec.md` · **Decisiones**: [research.md](research.md)

Esta funcionalidad **no cambia el modelo** de la spec 002
([data-model.md](../002-platform-data-model/data-model.md)). Define qué escribe la ingesta en
las tablas que ya existen y con qué reglas. Todas están en el esquema `core`.

## 1. Qué escribe cada proceso

| Tabla | Feed en vivo (`producer`) | Carga del catálogo (`catalog-loader`) |
|---|---|---|
| `extraction` | Una fila por consulta | Una fila por recuento y una por descarga |
| `raw_payload` | Cuerpo comprimido, una vez por huella (`encoding = 'gzip'`) | Huella y ruta del fichero (`encoding = 'file'`) |
| `excluded_event` | Versiones que no son terremotos | Ídem, si la fuente devuelve alguna |
| `publish_state` | Tras cada confirmación de Kafka | Ídem |
| `event_current`, `event_version`, `quarantine`, `message_log` | No las escribe: lo hace el consumidor a partir de los mensajes | Ídem |

## 2. `core.extraction`: valores por caso

| Caso | `source` | `purpose` | `outcome` | `http_status` | Recuentos | `content_sha256` | `error_detail` |
|---|---|---|---|---|---|---|---|
| Feed correcto | `usgs_feed` | `live` | `ok` | 200 | los cuatro | huella de `features` | nulo, o descripción de elementos no identificables |
| Feed sin cambios | `usgs_feed` | `live` | `not_modified` | 304 | nulos | huella del último contenido | nulo |
| Error de respuesta (429, 5xx, 4xx) | según proceso | según proceso | `http_error` | último código | nulos | nulo | código y, si existe, `Retry-After` |
| Tiempo agotado o sin conexión | según proceso | según proceso | `timeout` | nulo | nulos | nulo | tipo de fallo |
| Cuerpo ilegible | según proceso | según proceso | `invalid_json` | 200 | nulos | huella de los bytes | error de análisis |
| Estructura no válida | según proceso | según proceso | `invalid_structure` | 200 | nulos | huella de los bytes | qué falta |
| Recuento del catálogo | `usgs_catalog` | `historical_load` o `gap_recovery` | `ok` | 200 | `record_count` = recuento declarado | nulo | nulo |
| Descarga del catálogo | `usgs_catalog` | ídem | `ok` | 200 | los cuatro | huella del fichero | nulo |

Campos comunes: `request_url` (dirección completa), `requested_at` (inicio de la consulta),
`duration_ms` (total, con reintentos y esperas), `attempt_count`, `source_generated_at`
(`metadata.generated`, cuando hay cuerpo válido).

Solo en el catálogo: `window_start` y `window_end` (intervalo `[inicio, fin)`) y
`request_params`:

```json
{"endpoint": "query", "starttime": "2025-01-01T00:00:00Z", "endtime": "2025-02-01T00:00:00Z",
 "minmagnitude": 4, "eventtype": "earthquake", "orderby": "time-asc"}
```

`endpoint` vale `count` o `query`.

### Reglas

- `record_count = earthquake_count + excluded_count` en toda consulta con cuerpo válido de
  eventos (FR-003).
- `earthquake_count`: elementos identificables de tipo `earthquake`. `excluded_count`: los de
  otro tipo o sin tipo, más los no identificables (sin `id` o sin `updated` legible).
- `published_count`: versiones confirmadas por Kafka en ese ciclo. Nulo si el ciclo se
  interrumpió antes de terminar de publicar.
- La fila se inserta al conocer el resultado, antes de publicar; después solo se actualiza
  `published_count`. Si la base no está disponible en ese momento, el resultado queda pendiente
  en memoria y se inserta, con su `requested_at` original, antes de la siguiente consulta a la
  fuente (FR-001a).
- Los elementos no identificables cuentan en `excluded_count` pero no generan fila en
  `excluded_event`: por eso `excluded_count` puede ser mayor que las exclusiones guardadas de
  esa consulta, y la diferencia está descrita en `error_detail` (FR-011).
- `last_ingestion` = `max(requested_at)` con `source = 'usgs_feed'` y `outcome` en (`ok`,
  `not_modified`) (FR-014).

## 3. `core.raw_payload`

| Origen | `content_sha256` | `encoding` | `body` | `file_path` | `byte_size` |
|---|---|---|---|---|---|
| Feed, respuesta válida | SHA-256 de `features` en forma canónica | `gzip` | respuesta completa comprimida | nulo | bytes sin comprimir |
| Feed o catálogo, respuesta ilegible o no válida | SHA-256 de los bytes recibidos | `gzip` | bytes recibidos comprimidos | nulo | bytes recibidos |
| Catálogo, descarga correcta | SHA-256 de los bytes del fichero | `file` | nulo | ruta relativa a `data/` | tamaño del fichero |

- Forma canónica: JSON con claves ordenadas, separadores `,` y `:` sin espacios, UTF-8.
- Inserción: `ON CONFLICT (content_sha256) DO UPDATE SET last_seen_at = EXCLUDED.last_seen_at`.
  Un 304 actualiza `last_seen_at` del último contenido.
- Purga: `core.purge_raw_payload(RAW_PAYLOAD_RETENTION_DAYS)` cada 24 horas; elimina solo filas
  con `body`. Las de fichero no caducan.
- Ficheros: `data/usgs/catalog/<inicio>_<fin>_<filtro>_<huella12>.geojson`, por ejemplo
  `2025-01-01T000000Z_2025-02-01T000000Z_m4_earthquake_9b2d8cb824cb.geojson`; sin filtro, `all`.
  `<huella12>` son los 12 primeros caracteres de su SHA-256. El contenido es la respuesta de USGS
  sin modificar. Cada fichero es inmutable: una descarga nueva con otro contenido (USGS regenera
  `metadata` en cada respuesta) crea otro fichero en lugar de sobrescribir, así que toda huella
  registrada coincide siempre con su fichero, también con `--refresh` o con dos cargas a la vez.
  Las descargas anteriores se conservan en `data/`, que está fuera de Git.

## 4. `core.excluded_event`

| Columna | Valor |
|---|---|
| `event_id`, `updated_at` | `id` y `properties.updated` del elemento |
| `event_type` | `properties.type` tal como llegó; nulo si no venía |
| `reason_code` | `not_earthquake`, o `missing_type` si no trae tipo |
| `extraction_id` | Consulta en la que se vio por primera vez |
| `payload` | Elemento original |

Inserción con `ON CONFLICT (event_id, updated_at) DO NOTHING`: una versión excluida se guarda
una vez aunque aparezca en 1.440 consultas diarias.

## 5. `core.publish_state` y decisión de publicar

Compartido por feed y catálogo (research R6):

| Situación de una versión de terremoto | Decisión |
|---|---|
| Identificador desconocido | Publicar |
| `updated` posterior al registrado | Publicar |
| `updated` igual o anterior al registrado | No publicar (tampoco si llega por el catálogo: una versión atrasada no es una novedad) |

Se escribe tras la confirmación de Kafka, con la sentencia del contrato de la spec 002 (nunca
retrocede).

## 6. Huecos

No hay tabla de huecos: se derivan de `core.extraction` (research R10).

- **Hueco**: dos consultas consecutivas al feed con `outcome` en (`ok`, `not_modified`) cuyos
  `requested_at` distan más de 24 horas. Intervalo a recuperar:
  `[anterior − margen, siguiente − 24 h + margen)`.
- **Hueco abierto al arrancar**: la última consulta correcta dista más de 24 horas de la hora
  actual; el intervalo termina en `ahora − 24 h + margen`.
- **Recuperado**: las consultas con `purpose = 'gap_recovery'`, `outcome = 'ok'` y
  `request_params.endpoint = 'query'` hechas después del hueco cubren, unidas, todo el intervalo.

## 7. Ciclo de una consulta al feed

```text
petición ──► resultado ──► extraction (+ raw_payload) ──► excluded_event
                                   │
                                   └─► por cada versión de terremoto no publicada:
                                         enviar a Kafka ─► confirmación ─► publish_state
                                   └─► actualizar published_count ─► latido
```

Un fallo de la fuente termina en la fila de `extraction`; no toca `publish_state` ni ninguna
otra tabla (FR-017).

## 8. Para el diccionario de datos

Dos usos que la memoria debe reflejar al actualizar el diccionario de la spec 002:

- `extraction.error_detail`: además de fallos, describe los elementos no identificables de una
  consulta correcta.
- `extraction.request_params.endpoint`: `count` (recuento declarado) o `query` (descarga).
