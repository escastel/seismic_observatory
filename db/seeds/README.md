# Histórico de replay 2025

`historical_2025.jsonl` es el fixture académico reproducible usado por las
pruebas y la presentación. No se presenta como una descarga mundial exhaustiva:
contiene eventos válidos, un evento marítimo, rechazos WAF y dos versiones del
mismo identificador para demostrar idempotencia.

- Periodo: enero de 2025.
- Fuente: fixtures académicos reproducibles del proyecto.
- Formato: un objeto GeoJSON por línea.
- Filtro: solo eventos cuyo `time` pertenece a 2025.
- Conteo actual: 6 líneas no vacías.
- Deduplicación: el consumidor conserva una fila actual por `external_id` y
  `event_versions` conserva cada `(external_id, updated)`.

## Procedimiento para generar el histórico completo

La fuente reproducible es la API GeoJSON de USGS, consultada por meses para no
truncar resultados:

```text
https://earthquake.usgs.gov/fdsnws/event/1/query
  ?format=geojson&starttime=2025-01-01&endtime=2026-01-01
  &minlatitude=-90&maxlatitude=90&minlongitude=-180&maxlongitude=180
  &orderby=time-asc&limit=20000
```

La extracción debe registrar en este archivo la fecha UTC, URL final, conteo de
cada respuesta mensual, suma total y el SHA-256 del JSONL resultante. El
publicador lee todas las líneas no vacías, valida que cada evento pertenezca a
2025 y no aplica ningún límite de paginación. El fixture de seis líneas se
mantiene deliberadamente para que la demo local sea rápida y determinista.
