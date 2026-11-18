# Data Model: Consumidor y calidad de los datos

**Fecha**: 2026-11-16 · **Spec**: `spec.md` · **Decisiones**: [research.md](research.md)

La spec 002 define las tablas; esta funcionalidad las usa con las reglas de abajo y añade tres
cambios aditivos justificados en [research.md](research.md) R9, en la plantilla idempotente
`db/sql/041_consumer_quality.sql` (se aplica a `core` y a `replay`).

## 1. Cambios en el modelo

### `quarantine` (core y replay)

| Columna nueva | Tipo | Nulo | Significado |
|---|---|---|---|
| `reprocessed_at` | `timestamptz` | sí | Cuándo se reprocesó la fila. Nulo = pendiente |
| `reprocess_result` | `text` | sí | `recovered_new`, `recovered_revised`, `recovered_stale`, `recovered_duplicate` o `still_rejected`. `CHECK` en esos valores |
| `reprocess_reason_codes` | `text[]` | sí | Motivos vigentes si sigue rechazada; nulo si se recuperó |

Restricción: `reprocessed_at` y `reprocess_result` o ambos nulos o ambos presentes.

### `message_log` (core y replay)

| Cambio | Detalle |
|---|---|
| Columna `attempt smallint NOT NULL DEFAULT 0` | 0 = tratamiento original; 1 = reprocesado |
| Clave primaria | `(kafka_topic, kafka_partition, kafka_offset, attempt)` en lugar de sin `attempt` |
| `outcome` | `new`, `revised`, `stale`, `duplicate`, `quarantined` o **`excluded`** |

El consumidor escribe siempre `attempt = 0`; el reprocesado, `attempt = 1`. Un mensaje rechazado
cuya fila de reprocesado dice `new` aparece dos veces, con resultados distintos y distinguibles.

## 2. Qué escribe el consumidor, por caso

| Caso del mensaje | `event_current` / `event_version` | `quarantine` | `excluded_event` | `message_log.outcome` |
|---|---|---|---|---|
| Tratable, versión nueva | Sí, con marcas y país | — | — | `new` |
| Tratable, revisión posterior | Sí, sustituye estado y marcas | — | — | `revised` |
| Tratable, versión atrasada | Solo historial | — | — | `stale` |
| Tratable, versión ya vista | Sin cambios | — | — | `duplicate` |
| Tipo distinto de terremoto | — | — | Sí | `excluded` |
| Intratable (R2) | — | Una fila, todos los motivos | — | `quarantined` |
| El modelo rechaza la versión | — | Una fila, `model_constraint_violation` | — | `quarantined` |

El mensaje sintético añade `synthetic` a las marcas (o `is_synthetic` en cuarentena).

## 3. Reglas sobre los valores guardados

| Campo | Regla |
|---|---|
| `magnitude`, `depth_km` | Nulos de origen → `NULL`. Texto numérico → número y marca `*_from_text`. Texto no numérico → `NULL` y marca `*_not_numeric`. Nunca cero. Negativos se conservan |
| `mag_type`, `place` | `NULL` si faltan o vienen vacíos |
| `event_time`, `updated_at` | Milisegundos Unix → UTC; ilegibles → cuarentena |
| `country_id` | Entidad `ADM0_A3` que contiene el punto, la menor alfabéticamente si hay varias; `NULL` si ninguna |
| `quality_flags` | Marcas de [research.md](research.md) R4, sin repetidas, ordenadas alfabéticamente |

## 4. Códigos de motivo de cuarentena

`malformed_json`, `not_an_object`, `missing_id`, `invalid_id`, `missing_time`, `invalid_time`,
`missing_updated`, `invalid_updated`, `geometry_missing`, `geometry_not_point`,
`coordinates_missing`, `coordinates_not_numeric`, `coordinates_not_finite`,
`coordinates_out_of_range`, `model_constraint_violation`. Catálogo completo con dimensión y
justificación en [contracts/rules-catalog.md](contracts/rules-catalog.md).

## 5. Identificación de lo sintético

| Dónde | Cómo |
|---|---|
| `quarantine` | `is_synthetic = true` |
| `event_current`, `event_version` | Marca `synthetic` en `quality_flags` |
| `excluded_event` | Prefijo reservado `synthetic-` en `event_id` |

## 6. Filtro común de lo real

Todas las consultas de análisis real usan, según la tabla:

```sql
-- eventos y versiones
WHERE NOT ('synthetic' = ANY (quality_flags))
-- cuarentena
WHERE NOT is_synthetic
-- exclusiones
WHERE event_id NOT LIKE 'synthetic-%'
```

Las consultas de [db/queries/quality.sql](../../db/queries/quality.sql) los aplican y ofrecen la
variante «solo sintéticos».

## 7. Estados de una fila de cuarentena

```text
(creada, reprocessed_at nulo) ──reprocesado──► recuperada  (reprocess_result = recovered_*)
                                       └─────► sigue rechazada (still_rejected + motivos vigentes)
```

Ambas salidas son finales: el reprocesado solo toma filas con `reprocessed_at` nulo.
