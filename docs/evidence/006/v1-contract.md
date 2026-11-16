# V1 · Forma del contrato de /api/eventos

**Fecha**: 2026-11-16 18:54 UTC · **Rama**: `006-query-api` · **Resultado**: SUPERADA

Petición: `GET /api/eventos` sin parámetros, contra el sistema levantado (datos reales).

| Comprobación | Esperado | Observado | |
|---|---|---|---|
| Código y tipo | 200 application/json | 200 application/json | ✓ |
| Tipo de colección | FeatureCollection | FeatureCollection | ✓ |
| Claves de metadata | generated, last_ingestion, mode, count, total, truncated | ['count', 'generated', 'last_ingestion', 'limit', 'mode', 'next_offset', 'null_magnitude', 'offset', 'period', 'quarantined', 'total', 'truncated'] | ✓ |
| mode | live | live | ✓ |
| count = features devueltas | 186 | 186 | ✓ |
| Ventana por defecto | default_applied=true, ~24 h | {'start': 1794768843297, 'end': None, 'default_applied': True} | ✓ |
| Todos los eventos dentro de las últimas 24 h | time >= period.start | 186 features | ✓ |
| Coordenadas [lon, lat, prof] | 3 números finitos, lon en [-180,180], lat en [-90,90] | [-152.808, 60.253, 104.4] | ✓ |
| Tiempos enteros (ms) | int | int | ✓ |
| Sin eventos sintéticos | ningún id synthetic- | 0 | ✓ |
| Un evento una sola vez | ids únicos | 186 ids, 186 únicos | ✓ |
| Sin eventos | 200 con features: [] | 200 features=0 | ✓ |
| last_ingestion | ms de la última consulta correcta al feed (no nulo) | 1794855240682 | ✓ |

## Notas

- Ejemplo de respuesta: {"metadata": {"generated": 1794855243297, "last_ingestion": 1794855240682, "mode": "live", "count": 186, "total": 186, "truncated": false, "limit": 1000, "offset": 0, "next_offset": null, "period": {"start": 1794768843297, "end": null, "default_applied": true}, "null_magnitude": {"count": 0, "excluded": false}, "quarantined": {"total": 2, "invalid_geometry": 0}}, "feature": {"type": "Feature", "id": "aka2026wsqpvr", "geometry": {"type": "Point", "coordinates": [-152.808, 60.253, 104.4]}, "properties": {"mag": 1.4, "magType": "ml", "place": "67 km WNW of Ninilchik, Alaska", "time": 1794854914477, "updated": 1794854985170, "country_id": "USA", "country_name": "Estados Unidos", "continent": "North America", "subregion": "Northern America"}}}
