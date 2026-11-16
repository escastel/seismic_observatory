# V6 · Casos sintéticos controlados

**Salida**: [v6-synthetic.out](v6-synthetic.out) · **Consulta**:
[sql/v6-synthetic-cases.sql](sql/v6-synthetic-cases.sql) · **Contrato**:
[synthetic-cases.md](../../../specs/005-historical-replay/contracts/synthetic-cases.md)
(requisitos FR-016 a FR-018; criterio SC-005).

Orden: `reset` y `docker compose run --rm replay start --synthetic-only` (7 mensajes, sin selección ni
fila de extracción).

| # | Caso | Esperado | Observado (`message_log`) | Resultado |
|---|---|---|---|---|
| 1 | primera versión de `synthetic-replay-first` | `new` | `new` | ✔ |
| 2 | repetición exacta | `duplicate` | `duplicate` | ✔ |
| 3 | `synthetic-replay-revised`, versión 1 | `new` | `new` | ✔ |
| 4 | versión 2 (13:30, magnitud 4,4) | `revised` | `revised` | ✔ |
| 5 | `synthetic-replay-stale`, versión nueva (13:30) | `new` | `new` | ✔ |
| 6 | versión antigua tardía (12:10) | `stale` | `stale` | ✔ |
| 7 | latitud 145 | `quarantined` | `quarantined` | ✔ |

| Estado final | Esperado | Observado | Resultado |
|---|---|---|---|
| Recuento por resultado | new 3, duplicate 1, revised 1, stale 1, quarantined 1 | idéntico | ✔ |
| `replay.event_current` | 3 filas; `revised` con 4,4 y 13:30; `stale` sin retroceder (13:30) | `first` 4,1 · `revised` 4,4 13:30 · `stale` 13:30, todas con la marca `synthetic` | ✔ |
| `replay.event_version` | first 1, revised 2, stale 2 | idéntico | ✔ |
| `replay.quarantine` | 1 fila sintética con `coordinates_out_of_range` y el original | `is_synthetic` = t, `{coordinates_out_of_range}`, original conservado | ✔ |
| `core` | ninguna fila `synthetic-replay-%` | 0 en `event_current`, `event_version`, `quarantine` y `message_log` | ✔ |
| `replay compare` | `core` idéntico | salida 0 | ✔ |

Los sintéticos se excluyen del análisis con la condición `event_id NOT LIKE 'synthetic-%'` o
`NOT (quality_flags @> '{synthetic}')`, como ya hacen las consultas de la spec 004.
