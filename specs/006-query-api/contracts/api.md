# Contrato HTTP implementado (spec 006)

Desarrolla `resources/observatorio-sismico/CONTRATO-API.md`, que prevalece. Prefijo `/api`
(`API_PREFIX`). Solo métodos `GET` y `OPTIONS`. Tiempos en milisegundos Unix UTC.

## Parámetros comunes (eventos y estadísticas)

| Parámetro | Tipo | Por defecto | Regla |
|---|---|---|---|
| `mode` | `live` \| `replay` | `live` | otro valor → 422 |
| `start` | ISO 8601 con zona | solo `live`: 24 h antes de `end` (o de ahora si tampoco hay `end`) | inclusivo; sin zona → 422 |
| `end` | ISO 8601 con zona | sin cota | exclusivo; `start` ≥ `end` → 422 |
| `min_mag` | número finito | sin filtro | la magnitud nula no cumple |
| `country_id` | texto 1–8 alfanuméricos | sin filtro | |
| `exclude_synthetic` | booleano | `false` | solo tiene efecto en `replay` |

Solo eventos: `limit` (1 a `API_MAX_FEATURES`, por defecto el máximo = 1000) y `offset` (≥ 0).
Solo estadísticas: `baseline_year` (entero, por defecto 2025).

Parámetros desconocidos: se ignoran.

## GET /api/eventos

Siempre 200 con `FeatureCollection` (`Content-Type: application/json`).

```json
{
  "type": "FeatureCollection",
  "metadata": {
    "generated": 1793113200000,
    "last_ingestion": 1793113140000,
    "mode": "live",
    "count": 1,
    "total": 1,
    "truncated": false,
    "limit": 1000,
    "offset": 0,
    "next_offset": null,
    "period": {"start": 1793026800000, "end": null, "default_applied": true},
    "null_magnitude": {"count": 0, "excluded": false},
    "quarantined": {"total": 0, "invalid_geometry": 0}
  },
  "features": [{
    "type": "Feature",
    "id": "ejemplo",
    "geometry": {"type": "Point", "coordinates": [-3.7, 40.4, 12.0]},
    "properties": {
      "mag": 3.2, "magType": "ml", "place": "Ejemplo",
      "time": 1793109600000, "updated": 1793110000000,
      "country_id": "ESP", "country_name": "España",
      "continent": "Europe", "subregion": "Southern Europe"
    }
  }]
}
```

Con `mode=replay`, `metadata` añade `"label": "REPRODUCCIÓN"` y `"last_replayed_at"` (ms o
`null`), `metadata.mode` es `"replay"` y cada `properties` añade `replayed_at` (ms) y
`synthetic` (booleano). `last_ingestion` sigue siendo la última consulta correcta a USGS.

- `period`: periodo efectivo de la consulta (`default_applied: true` si se aplicó la ventana de 24 h). Con `end` y sin `start`, la ventana por defecto son las 24 h anteriores a `end`.
- Orden: `time` descendente, desempate por `id` ascendente. Una sola versión vigente por evento.
- `truncated = offset + count < total`. `next_offset = offset + count` o `null`.
- `null_magnitude.count`: eventos con magnitud nula que cumplen el resto de filtros;
  `excluded = true` si hay `min_mag` (no están en `features`).
- Sin resultados: `features: []`, `count: 0`, `total: 0`, 200.
- `quarantined`: filas de cuarentena no sintéticas del esquema del modo; `invalid_geometry` es el
  subconjunto por motivo de geometría.

## GET /api/estadisticas

200 con:

```json
{
  "mode": "live",
  "metadata": {"generated": 0, "last_ingestion": 0, "mode": "live"},
  "scope": "complete",
  "map_truncated": false,
  "period": {"start": 0, "end": 0, "default_applied": true},
  "filters": {"min_mag": null, "country_id": null, "exclude_synthetic": false},
  "unit": "events",
  "total": 0,
  "hourly": {"window": "1 hour UTC, end excluded", "items": [{"start": 0, "count": 0}]},
  "by_country": {"items": [{"country_id": null, "country_name": "Sin país asignado", "count": 0}]},
  "magnitude_distribution": {"unit": "magnitude (floor, 1 unit bins)", "items": [{"from": 4, "to": 5, "count": 0}], "unvalued": 0},
  "depth_distribution": {"unit": "km", "items": [{"label": "0-70", "from": 0, "to": 70, "count": 0}], "unvalued": 0},
  "comparison": {
    "recent": {"start": 0, "end": 0, "count": 0},
    "baseline": {"year": 2025, "events": 0, "days": 365, "daily_mean": 0.0},
    "ratio": "ND",
    "filters_applied": ["min_mag", "country_id", "exclude_synthetic"],
    "warning": "El periodo reciente puede estar incompleto: USGS añade y revisa eventos durante horas."
  }
}
```

- `metadata.last_replayed_at` y `label: "REPRODUCCIÓN"` aparecen con `mode=replay`; la respuesta
  nunca mezcla esquemas.
- `hourly.items`: una por hora UTC entre `period.start` y `period.end` (exclusivo), con ceros;
  más de 10.000 ventanas → 422.
- `total`: igual al `metadata.total` que devolvería `/api/eventos` con los mismos filtros.
- Los tramos de magnitud y profundidad suman `total - unvalued`.
- `ratio`: `recent.count / daily_mean`, o `"ND"` si `daily_mean` es 0.
- Se calcula siempre sobre el conjunto completo del filtro, no sobre una página.

## GET /api/salud

Siempre 200:

```json
{"status": "ok", "database": "ok", "replay_database": "ok", "generated": 0, "last_ingestion": 0}
```

`status` es `degraded` (y `database` o `replay_database` es `unavailable`) si falla algún pool;
entonces `last_ingestion` es `null`. Sin credenciales ni datos de conexión.

## Errores

| Situación | Código | Cuerpo |
|---|---|---|
| Parámetro inválido | 422 | `{"error": "invalid_parameters", "detail": [{"param": "start", "message": "..."}]}` |
| Base no disponible, pool sin abrir o tiempo agotado | 503 | `{"error": "database_unavailable", "detail": "..."}` |
| Error inesperado | 500 | `{"error": "internal_error", "detail": "..."}` |

Nunca se devuelve `features: []` con 200 por un fallo.

## Acceso

CORS solo para los orígenes de `CORS_ORIGINS` (exactos), métodos `GET` y `OPTIONS`, cabeceras
`Content-Type` y `ngrok-skip-browser-warning`, sin credenciales ni cookies. Rutas expuestas:
`/api/eventos`, `/api/estadisticas`, `/api/salud` y `/api/openapi.json`.
