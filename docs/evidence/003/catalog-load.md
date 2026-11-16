# Carga del histórico de 2025 (US2: V4, V5, V6)

- Observado (UTC): 2026-11-15T11:40Z a 2026-11-15T11:45Z
- Rama y commit: 003-usgs-ingestion @ 8bd7b46 más la carga del catálogo (sin commit al observar)
- Equipo: MINGW64_NT-10.0-26200 3.5.4-cbe555e0.x86_64 x86_64
- Motor: Docker 29.1.3 (Docker Desktop (containerized)), Compose 2.40.3-desktop.1; recursos del motor: 12 CPU, 7,6 GiB
- Fuente: catálogo real de USGS (`https://earthquake.usgs.gov/fdsnws/event/1`), conexión doméstica

## Resumen

| Escenario | Esperado | Observado | Resultado |
|---|---|---|---|
| V6 (subdivisión) | Los meses con más de 20.000 eventos aparecen divididos; nada se descarga | Ningún mes real supera el máximo, ni con todas las magnitudes y tipos (septiembre de 2026: 11.740; octubre: 11.321). La subdivisión se comprueba con pruebas automáticas (ver abajo) | SUPERADA con la salvedad indicada |
| V5 (reanudación) | Interrumpida a mitad, la misma orden termina sin repetir lo hecho | Cortada con `docker kill` tras 5 meses; la segunda ejecución reutilizó esos 5 (0 publicados) y descargó los 7 restantes | SUPERADA |
| V4 (carga de 2025) | Diferencia 0 con el total declarado; todo en `core` como `usgs_catalog`; nada en `replay`; ficheros fuera de Git con su huella; menos de 15 min | 18.302 eventos distintos = 18.302 declarados; 18.302 terremotos M ≥ 4 de 2025 en `core.event_current`, todos `usgs_catalog`, 0 en cuarentena, 0 filas en `replay`; 12 ficheros (13 MB) con huella igual a la registrada; 34 s + 56 s de orden | SUPERADA |
| V5 (repetición) | Ningún intervalo descargado de nuevo, 0 publicados, mismos recuentos | 12 intervalos «reutilizado», 0 publicados, diferencia 0; recuentos iguales antes y después | SUPERADA |

## V6. Subdivisión sin truncar

```text
$ docker compose run --rm catalog-loader --dry-run --all-magnitudes --all-types --start 2026-09-01 --end 2026-11-01
Periodo 2026-09-01T00:00:00Z → 2026-11-01T00:00:00Z · todas las magnitudes · todos los tipos
Intervalo                                     Declarados  Recibidos Terremotos Excluidos Publicados  Fichero
2026-09-01 00:00:00 → 2026-10-01 00:00:00          11740          —          —         —          —  prueba
2026-10-01 00:00:00 → 2026-11-01 00:00:00          11321          —          —         —          —  prueba
Prueba sin descarga: 2 intervalo(s), 23061 eventos declarados
exit=0
```

El quickstart esperaba meses por encima de 20.000; con los datos actuales de USGS no existe
ninguno, así que la división real no llega a activarse. Queda comprobada así:

- en la fuente real, una consulta que excede el máximo devuelve HTTP 400 «27066 matching events
  exceeds search limit of 20000» en lugar de truncar ([research.md](../../../specs/003-usgs-ingestion/research.md), 2026-11-15);
- `tests/unit/test_catalog_plan.py` divide por mitades hasta que cada parte cabe y falla con un
  error explícito si un intervalo de un segundo sigue excediendo el máximo;
- `tests/db/test_catalog_load.py::test_month_over_the_maximum_is_split_and_never_limited` carga
  con un máximo de 3 eventos: varios intervalos, ninguna petición con `limit`, todos los eventos.

## V5 y V4. Carga interrumpida y reanudada

Primera ejecución, cortada a mano a los 34 s (`docker kill loader-2025-first`):

```text
$ docker compose run --name loader-2025-first --rm catalog-loader
2025-01-01T00:00:00Z → 2025-02-01T00:00:00Z: declared 1413, received 1413, published 1413 (descargado)
2025-02-01T00:00:00Z → 2025-03-01T00:00:00Z: declared 1394, received 1394, published 1394 (descargado)
2025-03-01T00:00:00Z → 2025-04-01T00:00:00Z: declared 1178, received 1178, published 1178 (descargado)
2025-04-01T00:00:00Z → 2025-05-01T00:00:00Z: declared 1316, received 1316, published 1316 (descargado)
2025-05-01T00:00:00Z → 2025-06-01T00:00:00Z: declared 1228, received 1228, published 1228 (descargado)
real 0m33.388s
```

Segunda ejecución, la misma orden (11:42:01 → 11:42:57):

```text
$ docker compose run --rm catalog-loader
Periodo 2025-01-01T00:00:00Z → 2026-01-01T00:00:00Z · magnitud ≥ 4 · tipo earthquake
Intervalo                                     Declarados  Recibidos Terremotos Excluidos Publicados  Fichero
2025-01-01 00:00:00 → 2025-02-01 00:00:00           1413       1413       1413         0          0  reutilizado
2025-02-01 00:00:00 → 2025-03-01 00:00:00           1394       1394       1394         0          0  reutilizado
2025-03-01 00:00:00 → 2025-04-01 00:00:00           1178       1178       1178         0          0  reutilizado
2025-04-01 00:00:00 → 2025-05-01 00:00:00           1316       1316       1316         0          0  reutilizado
2025-05-01 00:00:00 → 2025-06-01 00:00:00           1228       1228       1228         0          0  reutilizado
2025-06-01 00:00:00 → 2025-07-01 00:00:00           1156       1156       1156         0       1156  descargado
2025-07-01 00:00:00 → 2025-08-01 00:00:00           2684       2684       2684         0       2684  descargado
2025-08-01 00:00:00 → 2025-09-01 00:00:00           2222       2222       2222         0       2222  descargado
2025-09-01 00:00:00 → 2025-10-01 00:00:00           1604       1604       1604         0       1604  descargado
2025-10-01 00:00:00 → 2025-11-01 00:00:00           1509       1509       1509         0       1509  descargado
2025-11-01 00:00:00 → 2025-12-01 00:00:00           1321       1321       1321         0       1321  descargado
2025-12-01 00:00:00 → 2026-01-01 00:00:00           1277       1277       1277         0       1277  descargado
Repetidos entre intervalos: 0
Eventos distintos:      18302
Declarados por USGS:    18302   (recuento del periodo completo al terminar)
Diferencia:             0
exit=0   real 0m56.051s
```

Tiempo de la orden (SC-006): 33 s + 56 s ≈ 1,5 min, muy por debajo de 15 min. El consumidor
terminó de almacenar los 18.302 mensajes unos 44 s después.

Comprobaciones en la base, con el consumidor ya al día:

```text
mensajes del catálogo en core.message_log: 18302 (todos outcome = new)
m4_2025_en_core (event_current, 2025, magnitude >= 4): 18302
procedencia de los eventos de 2025: usgs_catalog 18302
cuarentena del topic earthquakes.catalog: 0 filas
replay.event_current: 0 filas
```

Ficheros:

```text
$ git status --short data/
(sin salida)
$ ls data/usgs/catalog/
2025-01-01T000000Z_2025-02-01T000000Z_m4_earthquake_d6d8d7e96509.geojson
… (12 ficheros, uno por mes) …
2025-12-01T000000Z_2026-01-01T000000Z_m4_earthquake_dc83ea2e8648.geojson
summary-20261115T114257Z-76559a.json
$ du -sh data/usgs/catalog
13M
$ (cd data && sha256sum usgs/catalog/*.geojson)  frente a  core.raw_payload (encoding = 'file')
ficheros en disco: 12 · registrados: 12
todas las huellas coinciden
```

## V5. Repetición

```text
antes   (current|versions|descargas): 18575|18598|12
$ docker compose run --rm catalog-loader
… 12 intervalos «reutilizado», publicados 0 …
Eventos distintos:      18302
Diferencia:             0
exit=0   real 0m10.325s
después (current|versions|descargas): 18575|18598|12
```

`event_current` incluye además los 273 terremotos del feed en vivo.
