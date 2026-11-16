# Investigación: reproducción acelerada de una selección histórica

Decisiones que el plan necesitaba y que la spec dejó abiertas, más las que surgieron al leer el
código de las specs 002 a 004. Cada una indica qué se eligió, por qué y qué se descartó.

## R1. Quién fija `replayed_at`

- **Hecho**: hoy el consumidor pone `datetime.now()` al leer del topic de reproducción
  ([consumer/app/main.py:209](../../consumer/app/main.py#L209)). La spec pide que la orden añada
  el instante de reproducción al mensaje.
- **Decisión**: el productor de la reproducción escribe `replayed_at` (UTC, ISO 8601) en el mensaje
  en el momento de publicarlo; el consumidor usa ese valor si el topic es el de reproducción y el
  campo es una fecha válida, y si no, la hora de lectura como hasta ahora.
- **Por qué**: el instante de reproducción pertenece a quien reproduce y no cambia si el consumidor
  se reinicia o va con retraso; así el mismo mensaje relee con el mismo `replayed_at` y el
  reprocesado es idempotente. Es un cambio de una línea, sin tocar reglas ni modelo.
- **Descartado**: dejar la hora de lectura (cambia con cada reinicio del consumidor y no refleja la
  orden); un campo nuevo en el modelo (innecesario: `replay.event_current.replayed_at` ya existe).

## R2. «Zona» de la selección

- **Decisión**: un recuadro geográfico opcional (`--bbox min_lon,min_lat,max_lon,max_lat`), sin
  cruce del antimeridiano (se rechaza con un mensaje claro).
- **Por qué**: la selección se hace sobre los ficheros descargados, que no traen país; asignarlo
  exigiría cargar GeoPandas en el productor o duplicar la integración espacial del consumidor
  (principio IV). El recuadro es determinista, verificable y sin dependencias.
- **Descartado**: filtro por país (el país se asigna después, en el consumidor); filtro por texto de
  `place` (la constitución lo prohíbe como origen del país).

## R3. Cómo se controla una reproducción en curso

- **Decisión**: la orden `start` corre en primer plano (`docker compose run --rm replay start …`) y
  lee cada 0,25 s un fichero `data/replay/control.json`; `pause`, `resume` y `stop` lo escriben y
  `status` lee `data/replay/status.json`, que `start` actualiza cada segundo. `data/` ya está
  montado en lectura y escritura en las herramientas e ignorado por Git.
- **Por qué**: funciona igual en Windows y Linux, sin señales POSIX ni puertos y sin nuevo servicio.
  La demostración usa dos terminales.
- **Descartado**: señales `SIGUSR1` (no portables con `docker compose run` en Windows); una API HTTP
  de control (añade superficie y un servicio); una tabla de control en PostgreSQL (cambia el modelo).

## R4. Una sola reproducción activa

- **Decisión**: `start` y `reset` toman un bloqueo asesor de PostgreSQL (`pg_try_advisory_lock`) en
  una conexión que `start` mantiene mientras corre. Si el bloqueo está ocupado, `start` rechaza la
  orden; `reset` rechaza vaciar mientras hay una reproducción activa.
- **Por qué**: se libera solo si el proceso muere (nunca queda un «candado huérfano») y no necesita
  tablas nuevas.
- **Descartado**: fichero de bloqueo (queda huérfano si el contenedor se mata); tabla de estado.

## R5. Qué se compara para demostrar el aislamiento

- **Decisión**: la instantánea guarda, para cada tabla del esquema `core` (descubiertas por el
  catálogo, no listadas a mano), el recuento y la suma de `hashtextextended(fila::text, 0)`. La
  suma es independiente del orden y barata. En `core.extraction` se excluyen las filas con
  propósito `replay_selection`, que son la constancia legítima de la selección.
- **Condición**: el productor en vivo debe estar parado durante la comprobación, porque el feed real
  escribe en `core` por su cuenta. El procedimiento lo indica y la evidencia lo registra.
- **Descartado**: comparar solo recuentos (no detecta una fila alterada); `md5(string_agg(...))`
  (ordena y consume memoria con decenas de miles de filas).

## R6. Cadencia

- **Decisión**: `--rate` en eventos por segundo (por defecto 50) y `--speedup` opcional. Con solo
  `--rate`, el intervalo es `1/rate`. Con `--speedup`, el intervalo entre dos eventos es su
  diferencia de tiempo original dividida por el factor, y si además hay `--rate`, el intervalo es
  `max(original/factor, 1/rate)`: la cadencia nunca supera la velocidad indicada. Los plazos son
  absolutos (reloj monótono) para que el retraso del envío no se acumule; tras una pausa se
  rebasan para no «ponerse al día» a ráfagas.
- **Por qué**: sin factor se obtiene un ritmo constante de demostración; con factor se conserva la
  forma temporal del histórico (los terremotos en ráfaga siguen en ráfaga).
- **Descartado**: dormir un intervalo fijo tras cada envío (acumula el retraso del envío).

## R7. Cómo se registra la selección en `core.extraction`

- **Hecho**: `core.extraction` exige `source ∈ {usgs_feed, usgs_catalog}`, `request_url` no nulo y
  `outcome` válido; admite `purpose = 'replay_selection'`. No hay consulta a USGS.
- **Decisión**: una fila con `source = 'usgs_catalog'`, `purpose = 'replay_selection'`,
  `request_url = 'local-catalog:data/usgs/catalog'`, `outcome = 'ok'`, `window_start/end` del
  periodo, `request_params` con periodo, magnitud mínima, recuadro, ficheros usados con su huella y
  el número de eventos sin magnitud descartados por el filtro, `record_count` y `earthquake_count` =
  número de eventos seleccionados, `published_count` actualizado al terminar y `content_sha256` =
  huella del conjunto ordenado de pares (`id`, `updated`) de la selección.
- **Por qué**: usa el modelo tal cual, deja la selección localizable por SQL y permite reconstruirla.
- **Descartado**: ampliar el CHECK de `source` con un valor nuevo (cambio de modelo sin necesidad).

## R8. Fiabilidad de la selección

- **Decisión**: la selección **falla sin publicar nada** si: un fichero no coincide con la huella
  de `core.raw_payload` (principio V); el periodo pedido no está cubierto por las cargas
  `historical_load` registradas; o la magnitud mínima pedida es inferior a la de la carga que
  cubre el periodo. La cobertura y la magnitud de cada carga salen de `core.extraction`
  (`window_start/end` y `request_params`), no del nombre del fichero.
- **Por qué**: una selección que se queda corta en silencio contradice el principio V (nunca
  truncar en silencio) y daría una demostración con huecos que parecerían datos reales. Un evento
  presente en dos ficheros se deduplica por `id` quedándose con el `updated` mayor.

## R9. Material heredado

- **`producer/app/replay.py`**: se sustituye por el paquete `producer/app/replay/`. Su única
  función (publicar un JSONL a ritmo fijo) queda cubierta y ampliada; no se conserva.
- **`db/seeds/historical_2025.jsonl`** (seis eventos ficticios): se retira. Sus casos útiles
  (versiones del mismo identificador, rechazos) los cubre el conjunto sintético de esta spec, con
  la convención de la 004 y resultados esperados comprobables.
- **`db/seeds/historical_1900.jsonl`** (35 eventos reales descargados): se retira de Git, porque
  es un conjunto descargado y el procedimiento de la 003 lo regenera
  (`docker compose run --rm catalog-loader`). No lo usa ninguna prueba.
- **`db/seeds/README.md`**: se actualiza para reflejarlo. `db/seeds/*.jsonl` sigue ignorado.
- **Por qué**: «nada de conjuntos descargados en Git» y un solo mecanismo de reproducción en vez de
  dos con resultados distintos.

## R10. Conjunto sintético

- **Decisión**: se genera por código con fechas fijas (no relativas a «ahora») para que el
  resultado esperado sea idéntico en cada ejecución. Convención de la 004: identificador
  `synthetic-replay-…`, `"synthetic": true` y `"synthetic_case"`. Se publica al final de la
  selección con `--synthetic`, o solo con `--synthetic-only` (sin selección ni fila de extracción).
  Siete mensajes, cinco casos: ver [contracts/synthetic-cases.md](contracts/synthetic-cases.md).
- **Por qué**: el orden exacto importa (la versión antigua tardía debe llegar después de la
  nueva), de modo que no puede quedar mezclado por tiempo con el histórico.

## R11. Reinicio del consumidor y relectura del topic

- **Hecho**: el topic de reproducción conserva sus mensajes durante `KAFKA_RETENTION_HOURS` (168).
  Tras `replay.reset()` los mensajes antiguos siguen en Kafka.
- **Consecuencia**: el consumidor existente conserva su offset de grupo y no relee lo antiguo; un
  grupo nuevo empezaría desde el principio (principio II) y repoblaría `replay` con reproducciones
  anteriores. Es coherente con el diseño y se documenta en el README; no afecta a `core`.

## R12. Pruebas

- Unitarias: cadencia (con y sin factor, con tope), filtros de selección, máquina de estados de
  control, mensaje (tiempo original intacto, `replayed_at`, modo, clave).
- Con base real: selección registrada en `core.extraction`; aislamiento (instantánea idéntica tras
  reproducir); sintéticos con resultados esperados; bloqueo de una sola reproducción activa;
  `reset` sin efecto en `core`; mismo identificador en `core` y `replay`.
- Con el sistema real (`verify-stack`): 5.000 o más eventos acelerados, reinicio del consumidor a
  mitad y repetición tras `reset`.
