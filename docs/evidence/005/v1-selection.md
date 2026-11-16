# V1 · Selección registrada y verificada

**Fecha**: 2026-11-16 · **Equipo**: Windows 11 (Git Bash), Docker Desktop · **Salida completa**:
[v1-selection.out](v1-selection.out) · **Consulta**: [sql/v1-registered-selections.sql](sql/v1-registered-selections.sql)

Requisitos cubiertos: FR-001 a FR-004, SC-002 (tamaño de la selección). Catálogo: 2025, magnitud ≥ 4,
28 ficheros mensuales en `data/usgs/catalog/`, registrados por la spec 003.

| # | Orden (`docker compose run --rm replay select …`) | Esperado | Observado | Resultado |
|---|---|---|---|---|
| 1 | `--start 2025-01-01 --end 2025-05-01 --min-mag 4.0` | ≥ 5.000 eventos, registrada | 5.301 eventos, primero 2025-01-01T00:13:22Z, último 2025-04-30T23:56:05Z, `extraction_id` 556, salida 0 | ✔ |
| 2 | `--start 2024-06-01 --end 2024-07-01` | Rechazo por periodo sin cobertura | «El periodo no está cubierto … falta desde 2024-06-01», salida 2, sin fila nueva | ✔ |
| 3 | `--min-mag 2.5` sobre un catálogo de magnitud ≥ 4 | Rechazo por magnitud insuficiente | «La magnitud mínima pedida (2.5) es inferior a la de la carga del catálogo (4)», salida 2 | ✔ |
| 4 | `--min-mag 9.9` | Selección vacía, 0 eventos, aviso | 0 eventos, «la selección está vacía», salida 0, fila registrada con 0 | ✔ |
| 5 | `--bbox=-125,32,-114,42` (California) | Solo eventos del recuadro | 3 eventos en enero, `bbox` guardado en los parámetros | ✔ |
| 6 | Copia del catálogo con un fichero alterado (`DATA_DIR=/data/v1-copy`) | Rechazo por huella | «El fichero … no coincide con su huella registrada: ha sido alterado», salida 2 | ✔ |

La copia del punto 6 se creó bajo `data/` (ignorado por Git), se alteró un byte **solo en la copia** y
se borró al terminar; el catálogo original no se tocó.

## Registro en `core.extraction`

Cuatro selecciones registradas (554, 556, 557, 558) con `purpose = 'replay_selection'`,
`request_url = 'local-catalog:data/usgs/catalog'`, `outcome = 'ok'`, el periodo, el número de eventos
(`record_count` = `earthquake_count`), la magnitud mínima, el recuadro y el número de ficheros usados.
Los rechazos (2, 3 y 6) **no** dejan fila: no hubo selección. `published_count` queda nulo porque
`select` no publica (lo fija `start` al terminar).

## Nota: fallo encontrado y corregido durante esta verificación

La primera ejecución de `select` falló con `ModuleNotFoundError: No module named 'producer'`:
`selection.py` importaba con la ruta de las pruebas (`producer.app…`) y en la imagen del productor el
paquete es `app`. Las pruebas unitarias no podían verlo. Se corrigió con imports relativos y se añadió
`tests/unit/test_replay_service_layout.py`, que importa cada módulo con la disposición de la imagen y
**falla** si se vuelve al import absoluto (comprobado: 2 fallos con el import roto, 8 verdes con el
arreglo).
