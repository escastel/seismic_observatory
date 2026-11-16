# Ampliación con 2026 (US6: V7)

- Observado (UTC): 2026-11-15T11:51Z a 2026-11-15T11:54Z
- Rama y commit: 003-usgs-ingestion @ 5ff0850
- Equipo: MINGW64_NT-10.0-26200 3.5.4-cbe555e0.x86_64 x86_64
- Motor: Docker 29.1.3 (Docker Desktop (containerized)), Compose 2.40.3-desktop.1; recursos del motor: 12 CPU, 7,6 GiB
- Fuente: catálogo real de USGS, conexión doméstica

| | V7 |
|---|---|
| Esperado | Diferencia 0 con el total declarado; el recuento de 2025 no cambia; ningún evento duplicado; los que ya trajo el feed conservan su versión más reciente; cada carga consta con su periodo, filtro y fecha |
| Observado | 14.225 recibidos = 14.225 declarados; 2025 sigue en 18.302; 0 identificadores duplicados; 18 eventos ya publicados por el feed no se republicaron y siguen como `usgs_feed`; las dos cargas constan por separado en `core.extraction` |
| Resultado | SUPERADA |

## Carga

```text
2025 antes: 18302
$ docker compose run --rm catalog-loader --start 2026-01-01 --end 2026-11-15      (11:51:43 → 11:52:51)
Periodo 2026-01-01T00:00:00Z → 2026-11-15T00:00:00Z · magnitud ≥ 4 · tipo earthquake
Intervalo                                     Declarados  Recibidos Terremotos Excluidos Publicados  Fichero
2026-01-01 00:00:00 → 2026-02-01 00:00:00           1247       1247       1247         0       1247  descargado
2026-02-01 00:00:00 → 2026-03-01 00:00:00           1079       1079       1079         0       1079  descargado
2026-03-01 00:00:00 → 2026-04-01 00:00:00           1366       1366       1366         0       1366  descargado
2026-04-01 00:00:00 → 2026-05-01 00:00:00           1522       1522       1522         0       1522  descargado
2026-05-01 00:00:00 → 2026-06-01 00:00:00           1191       1191       1191         0       1191  descargado
2026-06-01 00:00:00 → 2026-07-01 00:00:00           1488       1488       1488         0       1488  descargado
2026-07-01 00:00:00 → 2026-08-01 00:00:00           1618       1618       1618         0       1618  descargado
2026-08-01 00:00:00 → 2026-09-01 00:00:00           1576       1576       1576         0       1576  descargado
2026-09-01 00:00:00 → 2026-10-01 00:00:00           1239       1239       1239         0       1239  descargado
2026-10-01 00:00:00 → 2026-11-01 00:00:00           1558       1558       1558         0       1558  descargado
2026-11-01 00:00:00 → 2026-11-15 00:00:00            341        341        341         0        323  descargado
Repetidos entre intervalos: 0
Eventos distintos:      14225
Declarados por USGS:    14225   (recuento del periodo completo al terminar)
Diferencia:             0
exit=0   real 1m8.103s
```

En noviembre se publicaron 323 de 341: los otros 18 ya los había publicado el feed en vivo con
una versión igual o más reciente, y una versión atrasada no se publica como novedad (enunciado
§5.3, FAQ 10).

## Comprobaciones, con el consumidor al día

```text
mensajes del catálogo procesados: 32509 (= 18302 + 14225 − 18)
eventos_2025 (event_current):                     18302
m4_2026_hasta_15nov (event_current):              14225
  por procedencia: usgs_catalog 14207 · usgs_feed 18
ids_duplicados en event_current:                  0
```

Registro de procedencia de las dos cargas (recuento del periodo completo):

```text
        desde         |        hasta         | mag |    tipo    |     extraido     | consultas
----------------------+----------------------+-----+------------+------------------+-----------
 2025-01-01T00:00:00Z | 2026-01-01T00:00:00Z | 4   | earthquake | 2026-11-15 11:42 |         2
 2026-01-01T00:00:00Z | 2026-11-15T00:00:00Z | 4   | earthquake | 2026-11-15 11:52 |         1
```

La carga de 2025 tiene dos recuentos del periodo completo porque se ejecutó dos veces (V5,
repetición). El espacio real contiene ahora 2025 y 2026 hasta el 15-11 con magnitud ≥ 4, y las
últimas horas con todas las magnitudes (feed): la memoria lo indica y el análisis debe comparar
con el mismo filtro.
