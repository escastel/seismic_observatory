# Contrato de la carga del catálogo

Interfaz de la orden con la que una persona carga el histórico, lo amplía o recupera un hueco.
Es la única interfaz nueva que esta funcionalidad ofrece a quien opera el sistema.

## Invocación

```bash
docker compose run --rm catalog-loader [opciones]
```

`catalog-loader` es un servicio de Compose bajo el perfil `tools`: no arranca con
`docker compose up`. Usa la imagen del productor y necesita `kafka` y `postgres` sanos.

## Opciones

| Opción | Por defecto | Significado |
|---|---|---|
| `--start FECHA` | `2025-01-01` | Inicio del periodo, incluido. Fecha o instante ISO 8601 en UTC |
| `--end FECHA` | `2026-01-01` | Fin del periodo, excluido |
| `--min-magnitude N` | `4` | Magnitud mínima. `--all-magnitudes` la quita |
| `--event-type TIPO` | `earthquake` | Tipo pedido a la fuente. `--all-types` lo quita |
| `--purpose` | `historical_load` | `historical_load` o `gap_recovery`. Con `gap_recovery`, los valores por defecto pasan a todas las magnitudes y todos los tipos, y `--start` y `--end` son obligatorios |
| `--refresh` | no | Vuelve a descargar los intervalos aunque su fichero exista y su huella coincida |
| `--dry-run` | no | Muestra los intervalos y sus recuentos sin descargar ni publicar |
| `--gaps` | — | No carga nada: lista los huecos detectados y si están recuperados, con la orden para recuperar cada uno |

Sin opciones ejecuta la carga obligatoria: 2025, mundial, magnitud ≥ 4, tipo terremoto.

## Ejemplos

```bash
# Carga obligatoria de 2025
docker compose run --rm catalog-loader

# Ampliación: 2026 hasta una fecha, mismo filtro
docker compose run --rm catalog-loader --start 2026-01-01 --end 2026-11-15

# Huecos pendientes
docker compose run --rm catalog-loader --gaps

# Recuperar un hueco (la orden exacta la da el aviso del productor o --gaps)
docker compose run --rm catalog-loader --purpose gap_recovery \
  --start 2026-11-12T09:00:00Z --end 2026-11-13T22:00:00Z
```

## Comportamiento garantizado

- Divide el periodo en meses naturales (el primero y el último pueden ser parciales).
- Nunca acepta una respuesta truncada: subdivide el intervalo que exceda el máximo de la fuente
  y comprueba que cada descarga trae exactamente los eventos declarados.
- Registra cada petición en `core.extraction` y cada fichero en `core.raw_payload`.
- Guarda las respuestas sin modificar en `data/usgs/catalog/`.
- Publica en `earthquakes.catalog` solo las versiones que no estén ya publicadas y marca cada
  una tras la confirmación de Kafka.
- Repetir la misma orden no descarga de nuevo los intervalos completos ni publica nada ya
  publicado. Tras una interrupción, repetirla termina la carga.
- No publica una versión igual o anterior a la ya registrada para ese evento, aunque el feed
  la hubiera traído antes.
- Una petición fallida o ilegible queda registrada antes de que la orden termine con código 1.
- Dos ejecuciones simultáneas no dejan ficheros a medias ni eventos duplicados en el espacio
  real; pueden enviar algún mensaje repetido, que el consumidor absorbe.
- No toca el esquema `replay` ni el topic de reproducción.

## Salida

Progreso por intervalo en la salida estándar y, al terminar, un resumen:

```text
Periodo 2025-01-01T00:00:00Z → 2026-01-01T00:00:00Z · magnitud ≥ 4 · tipo earthquake
Intervalo                     Declarados  Recibidos  Terremotos  Excluidos  Publicados  Fichero
2025-01-01 → 2025-02-01            1413       1413        1413          0        1413  descargado
…
Repetidos entre intervalos: 0
Eventos distintos:      18302
Declarados por USGS:    18302   (recuento del periodo completo al terminar)
Diferencia:                 0
```

El mismo resumen se guarda como JSON en `data/usgs/catalog/summary-<fecha>.json`.

## Códigos de salida

| Código | Significado |
|---|---|
| 0 | Carga completa y diferencia cero |
| 1 | Error que impide terminar (fuente caída tras los reintentos, intervalo imposible de subdividir, broker o base no disponibles). Lo ya hecho se conserva; repetir la orden continúa |
| 2 | Argumentos no válidos (fin no posterior al inicio, periodo en el futuro, fecha ilegible). No se consulta la fuente |
| 3 | Carga terminada con diferencia distinta de cero entre lo recibido y lo declarado; el resumen la detalla |

## Aviso de hueco del productor

Al arrancar, si la última consulta correcta al feed dista más de 24 horas, el productor escribe
una línea de nivel `WARNING` con este formato estable y sigue trabajando:

```text
Ingestion gap detected: last successful feed request at <instante>; events between <inicio> and <fin> are not covered by the feed. Recover with: docker compose run --rm catalog-loader --purpose gap_recovery --start <inicio> --end <fin>
```
