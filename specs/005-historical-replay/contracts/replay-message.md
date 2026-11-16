# Contrato: mensaje del topic `earthquakes.replay`

Un mensaje por versión de evento. Clave Kafka = identificador del evento (UTF-8). Valor = JSON
compacto UTF-8. Extiende el mensaje de la spec 003 (`specs/003-usgs-ingestion/contracts/`): el
consumidor lee los campos de primer nivel, igual que en los otros topics.

| Campo | Tipo | Origen | Notas |
|---|---|---|---|
| `id` | texto | `feature.id` | Idéntico a la clave |
| `updated` | entero (ms Unix UTC) | `properties.updated` | **Original de USGS, sin modificar** |
| `time` | entero (ms Unix UTC) | `properties.time` | **Original de USGS, sin modificar** (FR-007) |
| `mag`, `place` | número o nulo, texto | `properties` | Nulos tal cual |
| `geometry` | objeto | `feature.geometry` | Sin modificar |
| `properties` | objeto | `feature.properties` | Sin modificar |
| `original_event` | objeto | `feature` completo | Se conserva íntegro |
| `source` | texto | constante `usgs_catalog` | Informativo; el consumidor deriva la fuente del topic |
| `ingested_at` | ISO 8601 UTC | instante de publicación | Igual que `replayed_at` |
| `mode` | texto | constante `replay` | |
| `extraction_id` | entero o nulo | fila `replay_selection` | Nulo en `--synthetic-only` |
| `replayed_at` | ISO 8601 UTC con `Z` | reloj del productor al publicar | Lo que el consumidor guarda (R1) |
| `replay_run` | texto | identificador de la ejecución | Informativo, para las consultas de evidencia |

Los mensajes sintéticos añaden `"synthetic": true` y `"synthetic_case": "<caso>"` como en la spec
004.

## Reglas

1. `time` y `updated` nunca se alteran para parecer recientes (principio VI). Una prueba compara,
   para cada mensaje, `time` y `updated` con los del fichero de origen.
2. El productor solo marca un mensaje como enviado tras la confirmación de Kafka (principio II);
   si Kafka rechaza uno, la ejecución pasa a `failed` y no publica los siguientes.
3. Solo la orden `replay` publica en este topic, siempre con `mode = "replay"`. El destino de un
   mensaje lo decide el topic, no el campo `mode`: un mensaje de este topic acaba en `replay` y uno
   de los otros topics en `core`, de modo que ninguno puede cruzar.
4. Orden de publicación: por `time` ascendente y `id` como desempate; los sintéticos van después,
   en el orden fijo de [synthetic-cases.md](synthetic-cases.md).
5. Un evento repetido en dos ficheros del catálogo se publica una sola vez, con el mayor `updated`.

## Efecto en el consumidor

- Topic de reproducción → `search_path = replay, core` → escritura en `replay.*`.
- `replayed_at` del mensaje se guarda en `replay.event_current.replayed_at` y, por la regla de la
  spec 002, es obligatorio. Si faltara o no fuera una fecha válida, el consumidor usa la hora de
  lectura (compatibilidad con mensajes anteriores).
- El resto del procesamiento (reglas, país, cuarentena, versiones) es el de la spec 004.
