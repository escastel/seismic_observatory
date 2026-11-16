# Modelo de datos: qué lee la API y cómo se proyecta

La spec 006 **no crea ni modifica tablas, columnas ni índices**. Este documento fija qué lee cada
endpoint y cómo se proyecta a la respuesta.

## Lectura por modo

| Modo | Pool (`search_path`) | Tablas de eventos | Dimensión | Consultas |
|---|---|---|---|---|
| `live` | `core` | `core.event_current`, `core.quarantine` | `core.dim_country` | `core.extraction` |
| `replay` | `replay, core` | `replay.event_current`, `replay.quarantine` | `core.dim_country` | `core.extraction` |

`core.extraction` (última ingesta) se lee siempre del esquema real, también en modo `replay`.

## Proyección de `event_current` a una `Feature`

| Columna | Destino | Regla |
|---|---|---|
| `event_id` | `id` | tal cual |
| `longitude`, `latitude`, `depth_km` | `geometry.coordinates` = `[lon, lat, depth]` | profundidad `null` si no hay; longitud y latitud siempre presentes (`NOT NULL` y rango en el modelo) |
| `event_time` | `properties.time` | milisegundos Unix UTC (entero) |
| `updated_at` | `properties.updated` | ídem |
| `magnitude` | `properties.mag` | `null` si nula |
| `mag_type` | `properties.magType` | `null` si nulo |
| `place` | `properties.place` | `null` si nulo |
| `country_id` | `properties.country_id` | `null` = sin país |
| `dim_country.name_es` | `properties.country_name` | `null` si no hay país; la agregación lo rotula «Sin país asignado» |
| `dim_country.continent`, `.subregion` | `properties.continent`, `.subregion` | `null` si no hay país |
| `replayed_at` | `properties.replayed_at` | solo en `replay`, ms Unix |
| `quality_flags`, `event_id` | `properties.synthetic` | solo en `replay`: `true` si el identificador empieza por `synthetic-` o `synthetic` está en `quality_flags` |

## Filtro común (mapa y estadísticas)

Un único constructor produce el `WHERE` a partir de `start`, `end`, `min_mag`, `country_id`,
`exclude_synthetic` y el modo:

| Condición | SQL | Índice |
|---|---|---|
| `start` | `event_time >= $n` | `event_current_event_time_idx` |
| `end` | `event_time < $n` | ídem |
| ventana por defecto (solo `live`, sin `start`) | `event_time >= now() - 24 h` | ídem |
| `min_mag` | `magnitude >= $n` (la nula no cumple) | `event_current_magnitude_event_time_idx` |
| `country_id` | `country_id = $n` | `event_current_country_event_time_idx` |
| real (solo `live`) | `NOT starts_with(event_id,'synthetic-') AND NOT ('synthetic' = ANY(quality_flags))` | filtro residual |
| `exclude_synthetic` (solo `replay`) | ídem | filtro residual |

Cuando falta `end` no hay cota superior (un evento futuro entra). El valor por defecto `now()` se
evalúa una vez por petición en Python y se devuelve en `period`.

## Última ingesta

```sql
SELECT max(requested_at) FROM core.extraction
WHERE source = 'usgs_feed' AND outcome IN ('ok', 'not_modified');
```

Coincide con el predicado de `extraction_last_ok_feed_idx` (índice parcial sobre `requested_at`).

## Cuarentena en `metadata`

```sql
SELECT count(*) AS total,
       count(*) FILTER (WHERE reason_codes && $1) AS invalid_geometry
FROM quarantine WHERE NOT is_synthetic;
```

con `$1 = {geometry_missing, geometry_not_point, coordinates_missing, coordinates_not_numeric,
coordinates_not_finite, coordinates_out_of_range}`. Contador global del esquema del modo.

## Entidades de respuesta

Ver [contracts/api.md](contracts/api.md): colección de eventos, estado de salud, resultado
estadístico, comparación histórica y error.
