# Contrato: orden `replay`

Servicio de Compose `replay` (perfil `tools`, imagen del productor). Nunca arranca con
`docker compose up`. Forma general:

```bash
docker compose run --rm replay <subcomando> [opciones]
```

En Git Bash de Windows no hace falta `MSYS_NO_PATHCONV=1`: ninguna opción recibe rutas de
contenedor.

## Subcomandos

### `select` — ver la selección sin publicar

```text
replay select --start 2025-01-01 --end 2025-04-01 --min-mag 4.0 [--bbox MIN_LON,MIN_LAT,MAX_LON,MAX_LAT]
```

Verifica los ficheros (R8), aplica los filtros, **registra la selección** en `core.extraction` y
escribe en la salida estándar el número de eventos, el primer y el último tiempo y el
`extraction_id`. No publica nada.

### `start` — reproducir

```text
replay start --start … --end … --min-mag …  [--bbox …]
             [--rate 50] [--speedup 3600] [--synthetic | --synthetic-only]
```

| Opción | Significado | Validación |
|---|---|---|
| `--start`, `--end` | periodo UTC, `end` excluido (`YYYY-MM-DD` o ISO 8601) | `end` > `start` |
| `--min-mag` | magnitud mínima; las magnitudes nulas no la cumplen y se cuentan | número finito |
| `--bbox` | recuadro opcional | `min` < `max`; sin cruce del antimeridiano |
| `--rate` | eventos por segundo máximos (por defecto 50, o `REPLAY_DEFAULT_RATE`) | > 0 y finito |
| `--speedup` | factor sobre el tiempo original; opcional | > 0 y finito |
| `--synthetic` | añade al final los 7 mensajes sintéticos | — |
| `--synthetic-only` | publica solo los sintéticos, sin selección ni extracción | excluye al resto de filtros |

Cadencia: ver R6 de [research.md](../research.md). Se ejecuta en primer plano, imprime el progreso
cada segundo y termina al publicar el último evento, al recibir `stop` o al fallar.

### `pause` / `resume` / `stop` / `status`

```text
replay pause     # no se publica más hasta resume; efectivo en menos de 2 s
replay resume    # continúa por el siguiente evento
replay stop      # termina; lo ya publicado se conserva
replay status    # estado, enviados, restantes, objetivo de velocidad
```

Se ejecutan desde otra terminal. Escriben en `data/replay/control.json` o leen
`data/replay/status.json` (ver [data-model.md](../data-model.md) §4). Sin reproducción activa,
`pause`, `resume` y `stop` terminan con código 3 y no escriben nada.

### `reset` — repetir desde cero

```text
replay reset
```

Llama a `replay.reset()` y no toca `core`. Rechaza la orden (código 4) si hay una reproducción
activa. No relanza nada: se vuelve a ejecutar `start`.

### `snapshot` / `compare` — aislamiento

```text
replay snapshot            # guarda recuento y suma de cada tabla de core
replay compare             # compara con la instantánea; código 0 si son idénticas
```

Ver [isolation-check.md](isolation-check.md).

## Códigos de salida

| Código | Significado |
|---|---|
| 0 | Correcto (incluye selección vacía, con aviso) |
| 1 | Error de uso: opción inválida |
| 2 | Selección rechazada: fichero alterado, periodo sin cobertura o magnitud mínima insuficiente |
| 3 | No hay reproducción activa a la que aplicar `pause`, `resume` o `stop` |
| 4 | Ya hay una reproducción activa (`start`) o la hay mientras se pide `reset` |
| 5 | Fallo de Kafka o de la base durante la ejecución (estado `failed`) |
| 6 | `compare` encontró diferencias en `core` |

## Mensajes de error (español)

Los textos de salida de la orden están en español; los identificadores, en inglés. Ejemplo:
`Selección rechazada: el periodo 2025-02-15/2025-02-20 no está cubierto por las cargas registradas`.
