# Migración del modelo y pruebas de aceptación con el sistema real (V2)

- Observado (UTC): 2026-11-16T13:00Z a 2026-11-16T13:12Z
- Rama y commit: 004-consumer-quality @ ecddfcc más el marcado por clave (sin commit al observar)
- Equipo: MINGW64_NT-10.0-26200 3.5.4-cbe555e0.x86_64 x86_64
- Motor: Docker 29.1.3 (Docker Desktop (containerized)), Compose 2.40.3-desktop.1; recursos del motor: 12 CPU, 7,6 GiB

| Escenario | Esperado | Observado | Resultado |
|---|---|---|---|
| Migración `041` sobre la base existente | Se aplica sin recrear el volumen, dos veces sin error, sin perder filas | Aplicada dos veces; `reprocess*` en `core` y `replay`; clave de `message_log` con `attempt`; 33.112 filas conservadas con `attempt = 0` | SUPERADA |
| §11 «Magnitud nula» | Se conserva como nula, sin cuarentena | `synthetic-null_magnitude`: `magnitude` nula, en `event_current`, sin fila de cuarentena | SUPERADA |
| §11 «Coordenadas inválidas» | Cuarentena con motivo; ningún punto | `invalid_coordinates` y `coordinates_out_of_range` en cuarentena con su motivo; ningún evento con esos identificadores | SUPERADA |
| §11 «Evento marítimo» | Sin país asignado; permanece en el análisis | `synthetic-maritime_event`: `country_id` nulo, en `event_current` | SUPERADA |
| Cada regla a su destino | 31 mensajes: 13 eventos, 16 cuarentena, 2 exclusiones | Exactamente 13, 16 y 2 | SUPERADA |
| Repetir la inyección | Ningún recuento cambia | «Publicados 0, omitidos (ya constan) 31» | SUPERADA |
| Lo sintético fuera del análisis real | Cuarentena real = 2 filas originales | 2 reales (`magnitude_out_of_range`), 16 sintéticas; las consultas reales no devuelven ninguna sintética | SUPERADA tras la corrección de abajo |

## 1. Estado de partida (el «antes»)

```text
cuarentena: {magnitude_out_of_range} · is_synthetic f · 2 filas
eventos_actuales 32.976 · versiones 33.110 · mensajes 33.112
mag_nula 0 · prof_negativa 5 · con_marcas 0 · sin_pais 25.353
message_log: new 32.976 · revised 134 · quarantined 2
```

## 2. Migración de la base existente

```bash
MSYS_NO_PATHCONV=1 docker compose exec -T postgres sh -c \
  'export PGUSER="$POSTGRES_USER"; /sql/apply.sh "$POSTGRES_DB" 041_consumer_quality.sql'     # dos veces
```

```text
core.reprocessed_at · core.reprocess_result · core.reprocess_reason_codes   (y los tres en replay)
core pk(message_log)   = kafka_topic,kafka_partition,kafka_offset,attempt
replay pk(message_log) = kafka_topic,kafka_partition,kafka_offset,attempt
filas_message_log=33112 attempt_0=33112
```

La segunda aplicación solo emite avisos «ya existe, se omite». Tras reconstruir el consumidor, los
cinco servicios quedaron `healthy` y los recuentos de `message_log` no cambiaron.

## 3. Inyección de los casos sintéticos

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm -e KAFKA_BOOTSTRAP_SERVERS=kafka:9092 \
  -e KAFKA_TOPIC_LIVE=earthquakes.live -e KAFKA_TOPIC_CATALOG=earthquakes.catalog \
  -e KAFKA_TOPIC_REPLAY=earthquakes.replay tests python -m tests.synthetic.inject
Publicados 31, omitidos (ya constan) 0
$ (segunda ejecución)
Publicados 0, omitidos (ya constan) 31
```

Eventos con sus marcas (todos llevan `synthetic`):

```text
synthetic-null_magnitude          magnitud nula · profundidad 10 · ESP · {synthetic}
synthetic-maritime_event          4,2 · 10 · país NULO · {synthetic}
synthetic-negative_depth          4,2 · −2,7 · ESP · {negative_depth,synthetic}
synthetic-magnitude_out_of_range  10,5 · {magnitude_out_of_range,synthetic}
synthetic-depth_out_of_range      profundidad 900 · {depth_out_of_range,synthetic}
synthetic-future_time             {future_time,synthetic}
synthetic-updated_before_time     {synthetic,updated_before_time}
synthetic-magnitude_from_text     4,2 · {magnitude_from_text,synthetic}
synthetic-magnitude_not_numeric   magnitud NULA · {magnitude_not_numeric,synthetic}
synthetic-depth_from_text · synthetic-depth_not_numeric (profundidad NULA) ·
synthetic-extra_coordinates · synthetic-synthetic                         (13 eventos)
```

Cuarentena (cada fila con su motivo, 16 en total): `coordinates_missing`,
`coordinates_not_numeric`, `coordinates_not_finite`, `coordinates_out_of_range` (×2),
`geometry_missing`, `geometry_not_point`, `invalid_id`, `invalid_time`, `invalid_updated`,
`missing_id`, `missing_time`, `missing_updated`, `model_constraint_violation` (fecha anterior
a 1900), `malformed_json` y `not_an_object`. Exclusiones: `synthetic-not_earthquake`
(`quarry blast`) y `synthetic-missing_type`.

El recuento del registro cuadra con las consultas de [quality.sql](../../../db/queries/quality.sql)
sobre datos reales:

```text
received 33112 · sum_of_outcomes 33112 · difference 0
```

## 4. Fallo encontrado y corregido

Las filas `malformed_json` y `not_an_object` quedaron con `is_synthetic = false`: un JSON ilegible
no puede llevar el marcador, y entraban en los recuentos reales (FR-025). Corrección: el
consumidor trata como sintético todo mensaje cuya **clave de Kafka** (el identificador del
evento) empiece por el prefijo reservado `synthetic-`, aunque su cuerpo no se pueda leer
(`consumer/app/main.py`, `_mark_synthetic_key`). Dos pruebas nuevas en
`tests/db/test_consumer_rules.py` lo cubren (cuerpo ilegible y evento legible con esa clave).

Las dos filas ya inyectadas se corrigieron con un `UPDATE` de `is_synthetic` sobre esas dos
filas, que eran de prueba (no se borró nada):

```text
reales: 2 · {magnitude_out_of_range},{magnitude_out_of_range}
sinteticas: 16
```
