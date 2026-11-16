# Contrato de los mensajes publicados

Mensajes que el productor y la carga del catálogo envían a Kafka y que el consumidor procesa.
Fija lo que el enunciado exige en §5.4 sin cambiar lo que el consumidor ya lee.

## Topics y destino

| Topic | Quién publica | `source` | Destino |
|---|---|---|---|
| `earthquakes.live` | productor (feed) | `usgs_feed` | esquema `core` |
| `earthquakes.catalog` | carga del catálogo (histórico y huecos) | `usgs_catalog` | esquema `core` |
| `earthquakes.replay` | no se usa en esta funcionalidad (spec 005) | — | esquema `replay` |

## Clave

`event_id` (el `id` del elemento de USGS), en UTF-8. Todas las versiones de un evento van a la
misma partición y conservan su orden.

## Valor

JSON en UTF-8, sin `NaN` ni infinitos:

```json
{
  "id": "us7000abcd",
  "updated": 1794705713000,
  "time": 1794702000000,
  "mag": 4.6,
  "place": "10 km S of Somewhere",
  "geometry": {"type": "Point", "coordinates": [-70.1, -33.4, 35.0]},
  "properties": { "…": "properties del elemento, sin modificar" },
  "source": "usgs_feed",
  "ingested_at": "2026-11-15T01:21:53.412000+00:00",
  "mode": "live",
  "extraction_id": 1234,
  "original_event": { "…": "elemento Feature de USGS completo, sin modificar" }
}
```

| Campo | Obligatorio | Significado |
|---|---|---|
| `id`, `updated`, `time`, `mag`, `place`, `geometry`, `properties` | sí | Copia de primer nivel de los campos que lee el consumidor; los tiempos, en milisegundos Unix como en USGS |
| `source` | sí | `usgs_feed` o `usgs_catalog` |
| `ingested_at` | sí | Momento en que el productor obtuvo el evento, ISO 8601 en UTC. El consumidor lo guarda como `produced_at` |
| `mode` | sí | `live` para datos reales, también los del catálogo. `replay` queda para la spec 005 |
| `extraction_id` | sí | Consulta de la que procede el mensaje |
| `original_event` | sí | Elemento original; el consumidor lo guarda como `payload` de la versión |

## Garantías del emisor

- Solo se publican elementos identificables de tipo `earthquake`.
- Una versión (`id`, `updated`) se publica como mucho una vez mientras conste en
  `core.publish_state`; si el proceso cae entre la confirmación de Kafka y la escritura del
  estado, puede reenviarse. El consumidor lo tolera (spec 002).
- No se publica una versión con `updated` anterior o igual al registrado para ese evento.
- El emisor no valida magnitud, coordenadas ni fechas: esa decisión es del consumidor (spec 004).

## Compatibilidad

Añadir campos no rompe el contrato. `source` pasa de `"USGS"` a los dos valores de la tabla; el
consumidor de la spec 002 no lee ese campo. Cambiar o quitar un campo exige actualizar este
documento y la spec del consumidor.
