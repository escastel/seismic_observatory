# V5 · Repetición tras `reset`

**Salida**: [v5-repeat.out](v5-repeat.out) · **Consulta**:
[sql/replay-state-fingerprint.sql](sql/replay-state-fingerprint.sql) (requisitos FR-009 y SC-007).

Punto de partida: la reproducción parcial de V4 (336 eventos). Orden: `reset`, y de nuevo
`start --start 2025-01-01 --end 2025-05-01 --min-mag 4.0 --rate 200`.

| Paso | Esperado | Observado | Resultado |
|---|---|---|---|
| `compare` antes del `reset` | `core` igual que en V2 | «core idéntico a la instantánea», salida 0 | ✔ |
| `reset` | solo se vacía `replay`; `core` no se toca | «Tablas de replay vaciadas; core no se ha tocado», `replay.event_current` = 0 | ✔ |
| Segunda reproducción completa | 5.301 eventos | 5.301 publicados, `extraction_id` 561 | ✔ |
| Huella de `replay.event_current` | idéntica a la de V2 | V2: **5.301 · 270575545300917288502**; V5: **5.301 · 270575545300917288502** | ✔ |
| `compare` después | `core` igual | idéntico, salida 0 | ✔ |

La huella cubre `event_id`, `event_time`, `updated_at`, magnitud, país y marcas de calidad. Excluye
`replayed_at`, que por construcción cambia en cada reproducción (es el instante en que se reproduce).
Cada repetición deja otra fila `replay_selection` en `core.extraction`, también por diseño.
