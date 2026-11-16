# Contrato: casos sintéticos de la reproducción

Siete mensajes, cinco casos, fechas fijas (no relativas a «ahora») para que el resultado sea el
mismo en cada ejecución. Identificador `synthetic-replay-<caso>`, `"synthetic": true` y
`"synthetic_case"`, según la convención de la spec 004. Todos los eventos ocurren en
2025-06-15 UTC y se publican, en este orden, después de la selección (`--synthetic`) o solos
(`--synthetic-only`).

## Mensajes y resultado esperado

| # | Caso | Evento | `updated` | Resultado esperado (`replay.message_log.outcome`) |
|---|---|---|---|---|
| 1 | primera versión | `synthetic-replay-first` | U1 = 2025-06-15 12:10 | `new` |
| 2 | repetición exacta | `synthetic-replay-first` | U1 (mensaje idéntico) | `duplicate` |
| 3 | revisión, versión 1 | `synthetic-replay-revised` | U1 | `new` |
| 4 | revisión, versión 2 | `synthetic-replay-revised` | U2 = 2025-06-15 13:30 | `revised` |
| 5 | versión antigua tardía, nueva | `synthetic-replay-stale` | U2 | `new` |
| 6 | versión antigua tardía, antigua | `synthetic-replay-stale` | U1 (anterior) | `stale` |
| 7 | cuarentena | `synthetic-replay-bad-coordinates` | U1 | `quarantined` |

El caso 7 lleva latitud 145: motivo `coordinates_out_of_range` (catálogo de la spec 004).
La revisión (caso 4) cambia la magnitud de 4,1 a 4,4 para que el cambio sea visible.

## Estado final esperado en `replay`

| Tabla | Esperado |
|---|---|
| `event_current` (eventos `synthetic-replay-%`) | 3 filas: `first` (mag 4,1), `revised` (mag 4,4, `updated` = U2), `stale` (`updated` = U2) |
| `event_version` | 5 filas: `first` 1, `revised` 2, `stale` 2 |
| `quarantine` | 1 fila: `is_synthetic`, motivo `coordinates_out_of_range`, original conservado |
| `message_log` (de los siete mensajes) | `new` 3, `duplicate` 1, `revised` 1, `stale` 1, `quarantined` 1 |
| `core.*` | sin ninguna fila `synthetic-replay-%` |

## Consultas de comprobación

```sql
-- resultado de cada mensaje, en orden de llegada
SELECT kafka_offset, event_id, updated_at, outcome
FROM replay.message_log WHERE event_id LIKE 'synthetic-replay-%' ORDER BY kafka_offset;

-- recuento por resultado: new 3, duplicate 1, revised 1, stale 1, quarantined 1
SELECT outcome, count(*) FROM replay.message_log
WHERE event_id LIKE 'synthetic-replay-%' GROUP BY outcome ORDER BY outcome;

-- estado actual: el stale no retrocede (updated = U2) y el revised tomó la versión nueva
SELECT event_id, magnitude, updated_at, quality_flags FROM replay.event_current
WHERE event_id LIKE 'synthetic-replay-%' ORDER BY event_id;

-- ninguno llegó a core
SELECT (SELECT count(*) FROM core.event_version WHERE event_id LIKE 'synthetic-replay-%') AS in_core;
```

Los nombres de columna son los de `db/sql/040_event_tables.sql` (`event_current.magnitude`,
`updated_at`, `quality_flags`; `quarantine.reason_codes`, `is_synthetic`; `message_log.outcome`).

## Exclusión del análisis

Cualquier consulta de análisis excluye los sintéticos con
`NOT (quality_flags @> ARRAY['synthetic'])` o con `event_id NOT LIKE 'synthetic-%'`, como ya
hacen las consultas de la spec 004.
