# V2 y V8 · Reproducción acelerada de más de 5.000 eventos

**Salida completa**: [v2-v3-replay-5000.out](v2-v3-replay-5000.out) · **Consultas**:
[sql/v2-replayed-data.sql](sql/v2-replayed-data.sql),
[sql/replay-state-fingerprint.sql](sql/replay-state-fingerprint.sql) · **Comprobación de tiempos**:
[check_original_times.py](check_original_times.py)

Orden: `docker compose run --rm replay start --start 2025-01-01 --end 2025-05-01 --min-mag 4.0 --rate 200`
(requisitos FR-005 a FR-007, FR-011, FR-014; criterios SC-002 y SC-004).

| Comprobación | Esperado | Observado | Resultado |
|---|---|---|---|
| Eventos publicados | = eventos de la selección (≥ 5.000) | 5.301 de 5.301, estado `finished`, salida 0 | ✔ |
| Cadencia | 200 eventos/s ±20 % | `started_at` 17:53:36,161 → `updated_at` 17:54:03,089 = 26,93 s → **196,8 eventos/s** (−1,6 %). La orden completa, con arranque del contenedor y selección, tardó 29,4 s | ✔ |
| Eventos actuales en `replay` | 5.301 distintos | `replay.event_current` = 5.301; `event_version` = 5.301; cuarentena 0; excluidos 0 | ✔ |
| Resultado de cada mensaje | 5.301 `new` | `message_log`: `earthquakes.replay` · `new` · 5.301 | ✔ |
| Tiempo original conservado | 0 diferencias con los ficheros | 5.301 coinciden, 0 difieren, 0 sin original (`time` y `updated` comparados con los GeoJSON descargados) | ✔ |
| `replayed_at` informado | 0 nulos; ninguna fecha desplazada | 0 nulos; `replayed_at` entre 17:53:36 y 17:54:03 (instante real de publicación); `event_time` sigue siendo de enero a abril de 2025 | ✔ |
| Origen identificable desde la base | todo viene del topic de reproducción | `event_version.kafka_topic = 'earthquakes.replay'` en las 5.301 filas | ✔ |
| Datos reales | `core` sin versiones del topic de reproducción | 0 filas de `core.event_version` con ese topic; 0 filas de `core.event_current` con `replayed_at` | ✔ |
| Mismo identificador en ambos esquemas | coexisten sin interferir | los 5.301 identificadores están también en `core`; cada esquema conserva su fila (`core_not_replayed` y `replay_is_replayed` verdaderos) | ✔ |

## Observación sobre «valores distintos»

El histórico reproducido sale del mismo catálogo que ya está cargado en `core`, así que los valores
de un mismo identificador coinciden en las 5 filas mostradas. Que **puedan ser distintos** sin
interferir lo demuestra la prueba `tests/db/test_replay_end_to_end.py::test_same_event_id_in_core_and_replay_keeps_each_value`
(magnitud 2,0 en `core` y 4,0 en `replay` para el mismo identificador, ambas intactas) y el caso
sintético `synthetic-replay-revised` de [V6](v6-synthetic.md).

## Observación sobre la cadencia

La cadencia medida es la del publicador (hasta la confirmación de Kafka de cada mensaje, un envío
tras otro). El consumidor mantuvo el ritmo: al terminar la publicación el retraso en
`earthquakes.replay` llegó a 0 con 5.301 mensajes consumidos.
