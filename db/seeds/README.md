# Históricos de replay

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

`historical_1900.jsonl` contiene el año completo más antiguo disponible en la
API USGS al momento de la extracción. USGS comienza su catálogo consultable en
1900; el lote contiene 35 eventos y se conserva separado del fixture 2025.
Extracción realizada el 2026-11-11 UTC; SHA-256:
`95F0BE1FC5D23ECDAE67D885DA75BCF6EFDB110A44BC11BE842C26BD99163927`.

`historical_2026.jsonl` contiene la extracción completa de USGS para el año
2026, incluyendo los registros de febrero y marzo que se usan para validar el
filtro del frontend. Contiene 121.619 líneas y ocupa aproximadamente 98 MB.
SHA-256:
`CAE97A0DC8FF484FDBE1B1134CFC7BC0F1880BBA5D142BA9F89BB60773470086`.
Se publicó en `terremotos_replay` el 2026-11-11 a 1.000 eventos por segundo;
el consumidor aplica las reglas WAF y persiste los eventos aceptados.

## Procedimiento para generar el histórico completo

La fuente reproducible es la API GeoJSON de USGS, consultada por meses para no
truncar resultados. El descargador ejecutable es:

```powershell
python -m producer.app.history --year 1900 --output db/seeds/historical_1900.jsonl
```

Para descargar todos los años disponibles en un intervalo, se genera un archivo
independiente por año. La extracción consulta cada mes y pagina en bloques de
20.000 eventos, por lo que no trunca meses con alta actividad:

```powershell
python -m producer.app.history --start-year 1900 --end-year 2026 `
  --output-dir db/seeds
```

Los archivos `historical_YYYY.jsonl` pueden reproducirse individualmente para
mantener el consumo y la persistencia controlables. El proceso de extracción es
reanudable a nivel de año: los archivos ya generados pueden conservarse y no es
necesario volver a descargarlos.

```text
https://earthquake.usgs.gov/fdsnws/event/1/query
  ?format=geojson&starttime=2025-01-01&endtime=2026-01-01
  &minlatitude=-90&maxlatitude=90&minlongitude=-180&maxlongitude=180
  &orderby=time-asc&limit=20000
```

La extracción debe registrar en este archivo la fecha UTC, URL final, conteo de
cada respuesta mensual, suma total y el SHA-256 del JSONL resultante. El
publicador lee todas las líneas no vacías y no aplica ningún límite de
reproducción. El año se puede validar con `--year 1900`; si se omite, se
infiere del contenido del archivo. El fixture de seis líneas se mantiene
deliberadamente para que la demo 2025 sea rápida y determinista.
