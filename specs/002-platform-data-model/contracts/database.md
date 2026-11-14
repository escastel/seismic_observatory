# Contrato de base de datos

Interfaz que el modelo ofrece a productor, consumidor y API. Los servicios dependen de este
contrato, no de detalles internos del SQL.

## Conexión

| Servicio | Rol | `search_path` |
|---|---|---|
| Productor (modo real) | `observatory_writer` | `core` |
| Productor (modo reproducción) | `observatory_writer` | `replay, core` |
| Consumidor, topics `earthquakes.live` y `earthquakes.catalog` | `observatory_writer` | `core` |
| Consumidor, topic `earthquakes.replay` | `observatory_writer` | `replay, core` |
| API, modo `live` | `observatory_reader` | `core` |
| API, modo `replay` | `observatory_reader` | `replay, core` |

Las sentencias usan nombres sin calificar. Cambiar de destino es cambiar el `search_path`, nunca
el texto de la consulta. Los servicios no ejecutan DDL.

## `apply_event_version`

```text
apply_event_version(
  p_event_id       text,
  p_source         text,          -- 'usgs_feed' | 'usgs_catalog'
  p_event_time     timestamptz,
  p_updated_at     timestamptz,
  p_magnitude      double precision,   -- puede ser NULL
  p_mag_type       text,               -- puede ser NULL
  p_longitude      double precision,
  p_latitude       double precision,
  p_depth_km       double precision,   -- puede ser NULL
  p_place          text,               -- puede ser NULL
  p_country_id     text,               -- puede ser NULL
  p_quality_flags  text[],
  p_payload        jsonb,
  p_kafka_topic    text,
  p_kafka_partition integer,
  p_kafka_offset   bigint,
  p_replayed_at    timestamptz DEFAULT NULL
) RETURNS text      -- 'new' | 'revised' | 'stale' | 'duplicate'
```

Garantías:

- Atómica: estado actual e historial cambian juntos o no cambian.
- Idempotente: llamarla N veces con los mismos argumentos deja el mismo estado que llamarla una.
- Monótona: el estado actual nunca retrocede a un `updated_at` anterior.
- Debe llamarse dentro de la transacción del consumidor, que confirma el offset después del
  commit.
- Falla con error de restricción si las coordenadas están fuera de rango, si algún número es NaN
  o infinito, si `p_country_id` no existe en `dim_country` o si la fecha queda fuera de
  `dim_date`. El consumidor debe haber enviado esos casos a cuarentena antes de llamarla.

## Cuarentena

`INSERT ... ON CONFLICT (kafka_topic, kafka_partition, kafka_offset) DO NOTHING`. Reprocesar un
mensaje no crea otra fila.

## Registro de mensajes

`INSERT INTO message_log ... ON CONFLICT (kafka_topic, kafka_partition, kafka_offset) DO NOTHING`
en la misma transacción que `apply_event_version` o que la fila de cuarentena. `outcome` toma el
valor devuelto por la función, o `quarantined`. `produced_at` es el `ingested_at` del mensaje.

## Transacción del consumidor por mensaje

1. Abrir la transacción con el `search_path` del topic.
2. Llamar a `apply_event_version` o insertar en `quarantine`.
3. Insertar en `message_log`.
4. Confirmar la transacción.
5. Confirmar el offset en Kafka.

Si algún paso de 1 a 4 falla, el offset no se confirma y el mismo mensaje se reintenta con
espera; el consumidor no pasa al siguiente. Un grupo de consumo sin offsets confirmados empieza
por el principio del topic.

## Estado de publicación

`INSERT ... ON CONFLICT (event_id) DO UPDATE ... WHERE EXCLUDED.updated_at > publish_state.updated_at`.
Se escribe solo después de la confirmación de Kafka.

## Funciones de mantenimiento

- `replay.reset()`: vacía las tablas de eventos de `replay`. No existe equivalente en `core`.
- `core.purge_raw_payload(retention_days integer) RETURNS integer`: elimina los cuerpos de
  `raw_payload` más antiguos que la retención y devuelve cuántos; no toca los registros de
  fichero ni `extraction`.

## Lecturas de la API

- Una fila de `event_current` por evento; el país se obtiene con `LEFT JOIN dim_country`.
- `country_id IS NULL` significa «Sin país asignado»; el texto lo pone la API o el panel.
- Los tiempos se devuelven al cliente en milisegundos Unix.
- `last_ingestion` es el `requested_at` más reciente de `core.extraction` con `source =
  'usgs_feed'` y `outcome` en (`ok`, `not_modified`).

## Compatibilidad

Añadir columnas anulables o índices no rompe el contrato. Cambiar la firma o los valores
devueltos por `apply_event_version`, renombrar columnas o cambiar el significado de un nulo
exige actualizar este documento y las specs que dependen de él.
