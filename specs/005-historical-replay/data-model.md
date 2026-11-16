# Modelo de datos: reproducción acelerada

**Sin cambios en el modelo de las specs 002 a 004**: ni tablas, ni columnas, ni restricciones, ni
funciones nuevas. Esta funcionalidad usa lo que ya existe y añade solo ficheros locales y un
formato de mensaje. Lo que sigue describe cómo se usa cada pieza.

## 1. Lo que ya existe y se reutiliza

| Pieza | Origen | Uso en la reproducción |
|---|---|---|
| Esquema `replay` con las mismas tablas de eventos que `core` | spec 002 | Destino de todo lo reproducido |
| `replay.event_current.replayed_at NOT NULL` | spec 002 | Marca todo dato reproducido (FR-014) |
| `core.event_current` con `CHECK (replayed_at IS NULL)` | spec 002 | Impide que una reproducción llegue a `core` |
| `replay.reset()` | spec 002 | Repetir desde cero (FR-009); no existe equivalente en `core` |
| `core.extraction.purpose = 'replay_selection'` | spec 002 | Registro de cada selección |
| `core.raw_payload` (`encoding = 'file'`) | spec 003 | Huella de cada fichero del catálogo |
| Regla de versiones (`new`, `revised`, `stale`, `duplicate`) y cuarentena | specs 002 y 004 | Resultado de los casos sintéticos |
| Convención sintética (`synthetic-`, marca `synthetic`, `is_synthetic`) | spec 004 | Identificar los casos controlados |

## 2. Registro de una selección en `core.extraction`

Una fila por selección (no por reproducción: repetir con la misma selección crea otra fila, porque
queda constancia de cada ejecución).

| Columna | Valor |
|---|---|
| `source` | `usgs_catalog` |
| `purpose` | `replay_selection` |
| `request_url` | `local-catalog:data/usgs/catalog` (no hay consulta a USGS) |
| `request_params` | JSON: `start`, `end`, `min_magnitude`, `bbox` (o nulo), `files` (lista de ruta relativa y huella), `without_magnitude_dropped` |
| `window_start`, `window_end` | periodo pedido (fin excluido) |
| `requested_at` | instante de la selección (UTC) |
| `outcome` | `ok` |
| `record_count`, `earthquake_count` | número de eventos seleccionados |
| `excluded_count` | 0 |
| `published_count` | se fija al terminar o detener con el número de mensajes confirmados por Kafka |
| `content_sha256` | huella SHA-256 del conjunto ordenado de pares `id:updated` |

Una selección vacía se registra con 0 eventos y no publica nada. Un fallo de verificación (R8) no
registra fila: no hubo selección.

## 3. Mensaje del topic de reproducción

Definido en [contracts/replay-message.md](contracts/replay-message.md). Resumen: el contenido del
mensaje de la spec 003 (`id`, `updated`, `time`, `mag`, `place`, `geometry`, `properties`,
`original_event`), con `mode = "replay"`, `extraction_id` de la selección, `replayed_at` y
`replay_run` (identificador de la ejecución). Clave Kafka = identificador del evento. El
`time` y el `updated` son los originales de USGS, sin tocar.

## 4. Ficheros de control y estado (`data/replay/`, ignorados por Git)

| Fichero | Escribe | Lee | Contenido |
|---|---|---|---|
| `control.json` | `pause`, `resume`, `stop` | `start` cada 0,25 s | `{"command": "pause" \| "resume" \| "stop", "requested_at": "<UTC>"}` |
| `status.json` | `start` cada segundo y al cambiar de estado | `status` | `{"run": "<id>", "state": "running" \| "paused" \| "stopped" \| "finished" \| "failed", "total": N, "sent": N, "remaining": N, "rate_target": x, "speedup": x\|null, "started_at", "updated_at", "extraction_id", "error": null\|"..."}` |
| `core-snapshot.json` | `snapshot` | `compare` | Por tabla de `core`: recuento y suma de comprobación (ver [contracts/isolation-check.md](contracts/isolation-check.md)) |

`control.json` se consume: `start` lo borra tras ejecutar la orden y al empezar, para que una orden
antigua no afecte a la reproducción siguiente.

## 5. Estados de una orden de reproducción

```text
          start
 (none) ─────────► running ──pause──► paused
                     ▲  │               │
                     │  └──resume◄──────┘
                     │
        running/paused ──stop──► stopped
        running ──último evento confirmado──► finished
        running/paused ──error de Kafka o de base──► failed
```

- `paused` no publica y no cambia el contador `sent`.
- `stopped`, `finished` y `failed` son terminales y liberan el bloqueo asesor.
- Una orden `start` mientras otro proceso mantiene el bloqueo termina sin publicar (R4).
- `reset` solo se admite en estado terminal o sin reproducción (el bloqueo debe estar libre).

## 6. Instantánea de aislamiento

Por cada tabla de `core` (catálogo de PostgreSQL, no lista fija): recuento de filas y suma de
`hashtextextended(fila::text, 0)`. En `core.extraction` se excluyen las filas con propósito
`replay_selection`. La comparación devuelve las tablas cuyo recuento o suma difieren; vacío =
aislamiento comprobado.

## 7. Identificabilidad de lo reproducido desde la base

Sin cambios de modelo, una fila es reproducción si y solo si cumple cualquiera de estas
condiciones, todas verificables por SQL:

1. está en una tabla del esquema `replay` (y `kafka_topic = 'earthquakes.replay'` en su
   `event_version`, `quarantine` y `message_log`);
2. `replay.event_current.replayed_at` no es nulo (siempre, por la restricción).

El modo `replay` viaja en el mensaje de Kafka (FR-014) pero el modelo no guarda el mensaje
completo: `event_version.payload` es el `Feature` original de USGS, sin transformar, y solo la
cuarentena conserva el mensaje entero. Por eso la identificación desde la base se apoya en el
esquema, `replayed_at` y el topic de origen, no en el campo `mode`.

Los sintéticos se distinguen además por `quality_flags @> '{synthetic}'` o `is_synthetic` en la
cuarentena (spec 004).
