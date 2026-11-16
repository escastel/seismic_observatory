# Contrato de las órdenes de reprocesado y de sintéticos

## Reprocesar la cuarentena

```bash
docker compose run --rm quality-reprocess [--dry-run]
```

Servicio `quality-reprocess` de Compose bajo el perfil `tools`, con la imagen del consumidor; no
arranca con `docker compose up`.

Para cada fila de `quarantine` con `reprocessed_at` nulo, en `core` y en `replay`:

1. Reconstruye el mensaje desde `payload` (o `raw_text` si no era JSON).
2. Aplica las reglas vigentes ([rules-catalog.md](rules-catalog.md)).
3. En una transacción, con el `search_path` del topic de la fila:
   - si el mensaje ya es tratable: `apply_event_version`; si no, vuelve a motivos;
   - inserta en `message_log` la fila con `attempt = 1`;
   - marca la fila: `reprocessed_at = now()`, `reprocess_result` y, si sigue rechazada,
     `reprocess_reason_codes`.

| `reprocess_result` | Significado |
|---|---|
| `recovered_new`, `recovered_revised`, `recovered_stale`, `recovered_duplicate` | Pasó las reglas; es el resultado de `apply_event_version` |
| `still_rejected` | Sigue siendo intratable con las reglas vigentes |

Garantías: idempotente (una segunda ejecución no cambia nada); no borra filas; conserva la fila
`attempt = 0`; respeta la regla de versiones; no toca `publish_state` ni Kafka. `--dry-run` lista
lo que haría y sale sin escribir.

Salida: una línea por fila y un resumen (`pendientes`, `recuperadas`, `siguen rechazadas`, por
espacio). Código de salida 0 si termina; 1 si falla la base (lo hecho se conserva y repetir
continúa).

## Inyectar los casos sintéticos

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m tests.synthetic.inject [--list]
```

Publica en `earthquakes.live` un mensaje por caso de `tests/synthetic/cases.py`, con
`"synthetic": true` y `"synthetic_case": "<caso>"`; los eventos llevan identificador
`synthetic-<caso>` (prefijo reservado). Omite los casos que ya constan en la base, así que repetir
la orden no aumenta ningún recuento. `--list` muestra cada caso con su resultado esperado.

## Mensaje sintético

Igual que un mensaje real ([contracts/messages.md de la 003](../../003-usgs-ingestion/contracts/messages.md))
más `synthetic` (booleano) y `synthetic_case` (texto). El consumidor añade la marca `synthetic` al
evento y a su versión, y `is_synthetic` a la cuarentena.
