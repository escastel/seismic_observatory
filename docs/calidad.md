# Evidencia manual de calidad

## Alcance y fuente

La fuente operacional es el GeoJSON `all_day.geojson` de USGS; el replay usa
`db/seeds/historical_2025.jsonl`. La evidencia se obtiene mediante consultas
SQL sobre PostgreSQL y se registra manualmente para evitar crear un generador
automático de informes, conforme a la constitución.

## Consultas reproducibles

```sql
SELECT COUNT(*) AS validos FROM fact_sismos;
SELECT COUNT(*) AS cuarentena FROM cuarentena;
SELECT quality_dimension, reason_code, COUNT(*)
FROM cuarentena GROUP BY quality_dimension, reason_code
ORDER BY quality_dimension, reason_code;
SELECT COUNT(*) - COUNT(DISTINCT external_id) AS duplicados
FROM event_versions;
SELECT COUNT(*) FROM fact_sismos
WHERE magnitude < 0 OR magnitude > 10
   OR longitude NOT BETWEEN -180 AND 180
   OR latitude NOT BETWEEN -90 AND 90;
SELECT COUNT(*) FROM fact_sismos
WHERE country = 'Sin país asignado' AND country_id IS NOT NULL;
```

## Dimensiones y regla 1-10-100

| Dimensión | Prevención (1) | Detección (10) | Corrección (100) |
|---|---|---|---|
| Completitud | esquema y validación de nulos | cuarentena por campo | revisión del payload original |
| Validez | rangos WAF | `reason_code` estable | corrección de fuente |
| Exactitud | tipos finitos | cuarentena de valores imposibles | reprocesamiento |
| Consistencia | contrato de evento | validación temporal y estructural | revisión de versiones |
| Unicidad | clave `external_id` | historial por `(external_id, updated)` | eliminación de duplicados |
| Frescura | política de timestamps | cuarentena `future_timestamp`/`event_too_old` | reingesta controlada |

Los resultados y denominadores deben copiarse a la memoria técnica después de cada
sesión de demostración, indicando fecha UTC, topic y rango consultado.
