# Quickstart: validar la reproducción acelerada

Guía de comprobación con el sistema real; cada escenario guarda esperado, observado y salida en
`docs/evidence/005/` con la skill `verify-stack`. Una prueba no está superada hasta que hay
evidencia. Contratos: [replay-cli.md](contracts/replay-cli.md),
[replay-message.md](contracts/replay-message.md),
[synthetic-cases.md](contracts/synthetic-cases.md),
[isolation-check.md](contracts/isolation-check.md).

## Requisitos previos

- `.env` derivado de `.env.example` (no se lee ni se imprime).
- `docker compose up --build -d` y los cinco servicios sanos.
- Catálogo 2025 con magnitud ≥ 4 descargado y registrado (spec 003):
  `docker compose run --rm catalog-loader`. Si `data/usgs/catalog/` ya está, no se repite.
- En Git Bash de Windows, `MSYS_NO_PATHCONV=1` delante de las órdenes que pasan rutas de contenedor
  (`/sql/...`); las de `replay` no lo necesitan.
- Para el aislamiento: `docker compose stop producer` (R5).

## V1. Selección registrada y verificada

```bash
docker compose run --rm replay select --start 2025-01-01 --end 2025-04-01 --min-mag 4.0
```

**Esperado**: número de eventos ≥ 5.000, primer y último tiempo dentro del periodo, un
`extraction_id` nuevo. En la base: una fila `purpose = 'replay_selection'` con los parámetros y el
mismo número de eventos.

Variantes que deben **rechazarse con código 2**: periodo fuera de lo descargado; `--min-mag 2.5`
sobre un catálogo de magnitud ≥ 4; un fichero del catálogo alterado a mano (en una copia).
Selección vacía (`--min-mag 9.9`): código 0, 0 eventos, nada publicado.

## V2. Reproducción acelerada de al menos 5.000 eventos

```bash
docker compose run --rm replay start --start 2025-01-01 --end 2025-04-01 --min-mag 4.0 --rate 200
```

**Esperado**: termina en menos de 60 s con estado `finished`; tras esperar al consumidor,
`SELECT count(*) FROM replay.event_current` = número de eventos distintos de la selección;
cadencia medida dentro de ±20 % de 200 eventos/s; todo `time` y `updated` coincide con el fichero.

## V3. Aislamiento

Procedimiento de [isolation-check.md](contracts/isolation-check.md) alrededor de V2.

**Esperado**: `compare` con código 0, 0 tablas con diferencias; mismo identificador presente en
`core` y `replay` con valores propios (consulta sobre un evento de enero de 2025 que esté en
ambos).

## V4. Control: pausar, reanudar, detener

Con V2 en marcha (a `--rate 20` para que dure):

```bash
docker compose run --rm replay pause    # status: paused, sent no cambia durante 5 s
docker compose run --rm replay resume   # sigue por el siguiente evento
docker compose run --rm replay stop     # status: stopped; lo publicado se conserva
```

**Esperado**: pausa efectiva en menos de 2 s; tras reanudar no hay saltos ni repeticiones
(`message_log` de `replay` sin offsets repetidos y con los eventos en orden de tiempo); `start`
simultáneo rechazado con código 4.

## V5. Repetición tras `reset`

```bash
docker compose run --rm replay reset
docker compose run --rm replay start --start 2025-01-01 --end 2025-04-01 --min-mag 4.0 --rate 200
```

**Esperado**: tras `reset`, `replay.*` vacío y `core` idéntico (V3); tras la segunda reproducción,
recuentos y suma de comprobación de `replay.event_current` iguales a los de V2. `reset` con una
reproducción activa: código 4.

## V6. Casos sintéticos

```bash
docker compose run --rm replay reset
docker compose run --rm replay start --synthetic-only
```

**Esperado**: las consultas de [synthetic-cases.md](contracts/synthetic-cases.md) devuelven
`new` 3, `duplicate` 1, `revised` 1, `stale` 1, `quarantined` 1; `core` sin ningún
`synthetic-replay-%`.

## V7. Reinicio del consumidor a mitad de la reproducción

```bash
docker compose run --rm replay start … --rate 100      # terminal 1
docker compose restart consumer                         # terminal 2, hacia la mitad
```

**Esperado**: el consumidor reanuda; al terminar, recuento y suma de `replay.event_current` iguales
a los de una ejecución sin reinicio (V2); sin duplicados de efecto (`message_log` sin repetidos).

## V8. Identificabilidad y mismo identificador en ambos esquemas

```sql
SELECT count(*) FROM replay.event_current WHERE replayed_at IS NULL;          -- 0
SELECT count(*) FROM replay.event_version WHERE kafka_topic <> 'earthquakes.replay'; -- 0
SELECT c.event_id, c.magnitude AS core_mag, r.magnitude AS replay_mag
FROM core.event_current c JOIN replay.event_current r USING (event_id) LIMIT 5;
```

**Esperado**: 0 y 0, y filas en la tercera consulta cuando se reproduce un periodo ya cargado en
`core`. Los valores de la tercera pueden ser iguales; la prueba de valores distintos con un evento
modificado la cubre `tests/db`.

## V9. Material heredado y repositorio

```bash
git ls-files db/seeds                 # sin historical_*.jsonl
git status --short                    # sin data/ ni ficheros descargados
```

**Esperado**: `db/seeds/` solo con `.gitkeep` y `README.md`; ningún conjunto descargado versionado;
README y `docs/report.md` con el procedimiento paso a paso.

## Pruebas automáticas

```bash
docker compose -f compose.yaml -f compose.dev.yaml --profile test run --rm tests pytest tests -q
```

Resultado completo guardado en `docs/evidence/005/tests.txt`.
