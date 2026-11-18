# Research: Ingesta desde USGS

**Fecha**: 2026-11-15 · **Spec**: `spec.md`

No quedaban marcadores NEEDS CLARIFICATION. Este documento fija las decisiones técnicas. Las
marcadas como **verificado** se comprobaron el 2026-11-15 con peticiones de solo lectura a los
servicios públicos de USGS (agente de usuario genérico, sin datos del proyecto) o leyendo el
código de la spec 002.

## Hechos observados en la fuente

| Hecho | Observación (**verificado**) |
|---|---|
| Feed `all_day.geojson` | 200 en 0,18 s; 137 kB sin comprimir, 17 kB con gzip; 192 elementos, todos `earthquake` y `Point` con 3 coordenadas |
| Cabeceras del feed | `Last-Modified` y `Cache-Control: public, max-age=60`; **no hay `ETag`**. `If-Modified-Since` con el valor recibido devuelve 304 |
| Dos consultas seguidas | Mismo cuerpo, mismo `metadata.generated`: la respuesta se sirve desde caché durante un minuto |
| Campos nulos en el feed | `tz` 100 %, `alert` 99 %, `mmi` 97 %, `felt` y `cdi` 92 %; `mag`, `magType`, `place` sin nulos en esa muestra |
| Retraso `updated − time` | mínimo 0,5 min, mediana 3,5 min, máximo 1.001 min |
| Catálogo, 2025, M ≥ 4, `earthquake` | **18.302** eventos; por meses: 1.413, 1.394, 1.178, 1.316, 1.228, 1.156, 2.684, 2.222, 1.604, 1.509, 1.321 y 1.277 (suman 18.302). Ningún mes supera el máximo |
| Catálogo, 2026 hasta el 15-11, mismo filtro | 14.218 eventos |
| Catálogo, todas las magnitudes y tipos | 456 eventos en 36 horas; 10.058 en 30 días |
| Punto de recuento | `…/count?format=geojson&…` devuelve `{"count": N, "maxAllowed": 20000}` en 0,3–1,4 s |
| Exceso sobre el máximo | `…/query` devuelve **HTTP 400** con el texto «N matching events exceeds search limit of 20000»; no trunca. Solo trunca si se pasa `limit` |
| Límites del intervalo | `starttime` incluido y `endtime` excluido: un evento justo en el límite cuenta solo en el intervalo que empieza en él (112 + 1 = 113) |
| Intervalo sin eventos | 200 con una colección vacía |
| `metadata` del catálogo | Incluye `generated`, `url`, `count` y `status` |

## R1. Cliente HTTP y política de reintentos

- **Decisión**: un único módulo `producer/app/usgs.py` hace todas las peticiones a USGS con
  `requests` (ya fijada) ejecutada en un hilo, y devuelve siempre un resultado estructurado
  (resultado, código HTTP, intentos, duración, cuerpo en bytes, detalle del error,
  `Last-Modified`); nunca lanza una excepción por un fallo de la fuente. Reintenta ante tiempo
  agotado, error de conexión, 429 y 5xx, hasta `USGS_MAX_ATTEMPTS` (4: una petición y tres
  reintentos), con espera de 1, 2 y 4 s o la que indique `Retry-After` (segundos o fecha HTTP)
  si es mayor.
- **`Retry-After` largo**: si la espera indicada supera 120 s, no se reintenta dentro del ciclo;
  la consulta se registra como fallida y no se vuelve a consultar la fuente hasta que pase el
  tiempo indicado. Así la espera nunca es inferior a la pedida (FR-015) sin dejar el ciclo
  bloqueado.
- **Razón**: FR-015 a FR-017 exigen registrar cada fallo con sus intentos; un resultado
  estructurado se convierte directamente en una fila de `core.extraction`. No se añade ninguna
  biblioteca.
- **Alternativas**: `aiohttp` (dependencia nueva sin necesidad); mantener `feed.py`, que lanza
  excepciones y pierde código, intentos y duración.

## R2. Petición condicional y resultado «sin cambios»

- **Decisión**: el productor envía `If-Modified-Since` con el último `Last-Modified` recibido.
  Un 304 se registra con `outcome = 'not_modified'`, la huella del último contenido conocido y
  sin recuentos; además actualiza `last_seen_at` de ese original para que no se purgue mientras
  siga vigente.
- **Razón**: la fuente lo admite (**verificado**) y FR-013 lo pide; ahorra 137 kB por consulta
  repetida. No hay `ETag`, así que es el único mecanismo disponible.
- **Alternativas**: ignorar las cabeceras y deduplicar solo por huella (funciona, pero descarga
  y analiza cuerpos idénticos).

## R3. Huella del contenido

- **Decisión**: para respuestas válidas del feed, la huella es el SHA-256 de la lista `features`
  serializada de forma canónica (claves ordenadas, separadores compactos, UTF-8). El cuerpo que
  se guarda en `core.raw_payload` es la respuesta original completa comprimida con gzip. Para
  respuestas ilegibles o con estructura no válida, la huella es el SHA-256 de los bytes
  recibidos. Para ficheros del catálogo, la huella es el SHA-256 de los bytes del fichero, de
  modo que se pueda comprobar con cualquier herramienta estándar.
- **Razón**: `metadata.generated` cambia en cada regeneración aunque los eventos sean los
  mismos; una huella del cuerpo completo no detectaría copias idénticas (decisión R10 de la
  spec 002). En los ficheros interesa lo contrario: verificar que el fichero no ha cambiado.
- **Alternativas**: huella del cuerpo completo para todo (guarda copias idénticas); huella por
  evento (no identifica una respuesta).

## R4. Cuándo se escribe la extracción

- **Decisión**: la fila de `core.extraction` se inserta en cuanto se conoce el resultado de la
  petición, antes de publicar nada, con los recuentos de recibidos, terremotos y excluidos. Tras
  publicar, se actualiza `published_count`. El original se guarda en la misma transacción que
  la extracción.
- **Razón**: si el proceso cae durante la publicación, la consulta y su original ya constan
  (FR-001, FR-004); `published_count` nulo indica un ciclo interrumpido.
- **Base no disponible tras la respuesta** (FR-001a): el resultado de la petición se guarda en
  memoria como pendiente; el ciclo reintenta registrarlo con la espera de `common/retry.py` y
  no vuelve a consultar la fuente hasta conseguirlo. Si el proceso se reinicia en ese intervalo,
  esa consulta se pierde: es el único caso sin registro y se documenta como limitación.
- **Alternativas**: una sola escritura al final del ciclo (un fallo a mitad no deja rastro).

## R5. Exclusiones y elementos no identificables

- **Decisión**: el productor escribe en `core.excluded_event` cada versión cuyo
  `properties.type` no sea `earthquake`, con `ON CONFLICT (event_id, updated_at) DO NOTHING`,
  `reason_code = 'not_earthquake'` (o `'missing_type'` si no trae tipo) y el `extraction_id` de
  la consulta en que se vio primero. Un elemento sin `id` o sin `updated` legible no puede
  identificarse: se cuenta dentro de `excluded_count`, se describe en `error_detail` de la
  extracción (cuántos y en qué posición de la respuesta) y queda en el original guardado.
- **Razón**: FR-010 y FR-011. La clave de `excluded_event` exige identificador y versión; y
  publicarlo sin clave lo repetiría cada minuto, porque el estado de publicación no puede
  recordarlo. Mantener `recibidos = terremotos + excluidos` (FR-003) hace comprobable que nada
  se pierde.
- **Alternativas**: una tabla nueva para elementos no identificables (cambio de modelo para un
  caso que USGS no produce); enviarlos a Kafka para que el consumidor los ponga en cuarentena
  (una fila de cuarentena por minuto).

## R6. Estado de publicación compartido

- **Decisión**: feed y catálogo comparten `core.publish_state`. Cualquiera de los dos publica
  una versión solo si su `updated` es posterior a la registrada para ese evento (FAQ 10), y la
  marca tras la confirmación de Kafka.
- **Razón**: hace repetible y reanudable la carga del catálogo sin estado propio (FR-024,
  FR-025): una segunda ejecución no encuentra nada que publicar. Un evento de 2025 que el feed
  ya trajo con una versión más reciente no se republica con una anterior.
- **Consecuencia documentada**: la procedencia de una versión es la del canal que la publicó
  primero. Si la base se recrea, el estado se pierde con ella y la carga vuelve a publicar todo,
  que es lo correcto.

## R7. Mensaje publicado

- **Decisión**: se mantiene la forma actual y se fijan los campos del enunciado §5.4: clave =
  `event_id`; `source` (`usgs_feed` o `usgs_catalog`), `ingested_at`, `mode` (`live`),
  `original_event`, más `extraction_id` y los campos de primer nivel que hoy lee el consumidor
  (`id`, `updated`, `time`, `mag`, `place`, `geometry`, `properties`). Ver
  [contracts/messages.md](contracts/messages.md).
- **Razón**: FR-008a; el consumidor no cambia (spec 004). Hoy `source` vale `"USGS"`; el
  consumidor no lo lee (deduce la procedencia del topic), así que precisarlo no rompe nada
  (**verificado** en `consumer/app/main.py`).

## R8. Carga del catálogo

- **Decisión**: un programa `python -m app.catalog_load` en la imagen del productor, con
  periodo, magnitud mínima, tipo y propósito como argumentos y la carga obligatoria como valores
  por defecto. Para cada mes del periodo:
  1. pide el recuento (`/count`); si supera `maxAllowed`, divide el intervalo en dos mitades y
     repite; se detiene con error si un intervalo de un segundo sigue excediendo el máximo;
  2. pide los eventos (`/query`, `orderby=time-asc`) y comprueba que recibe exactamente los que
     declaró el recuento; un 400 por exceso (el catálogo creció entre ambas peticiones) vuelve
     al paso 1;
  3. guarda la respuesta tal cual en `data/usgs/catalog/`, registra su huella y su ruta y la
     extracción;
  4. publica en `earthquakes.catalog` las versiones que `publish_state` no tenga.
  Al final pide el recuento del periodo completo y escribe el resumen (FR-026).
- **Reanudable y repetible**: un intervalo cuyo fichero existe y cuya huella coincide con la
  registrada no se vuelve a descargar («descarga una vez y reutiliza», enunciado §4.2); la
  publicación siempre se recalcula contra `publish_state`. La opción `--refresh` vuelve a
  descargar para actualizar la instantánea.
- **Deduplicación entre intervalos**: por `event_id` en memoria durante la ejecución, además del
  estado de publicación. Los límites son `[inicio, fin)` (**verificado**), así que no se esperan
  repeticiones, pero el enunciado pide no darlo por hecho.
- **Ejecuciones simultáneas**: no se impiden. Cada fichero se escribe en uno temporal y se
  renombra, así que nunca queda a medias; dos ejecuciones pueden publicar la misma versión dos
  veces, lo que el consumidor absorbe (`duplicate`); `publish_state` nunca retrocede.
- **Fallos del catálogo**: una petición fallida o ilegible se registra igual que en el feed
  (FR-001, FR-006) y la respuesta ilegible se conserva; la orden termina con código 1.
- **Recuentos también registrados**: las peticiones a `/count` son consultas a USGS y constan en
  `core.extraction` con `request_params.endpoint = "count"` (FR-001).
- **Razón**: 18.302 eventos en 12 peticiones de menos de 3.000 cada una; el recuento previo da a
  la vez la decisión de subdividir y el «total declarado por la fuente» de la comprobación.
- **Alternativas**: paginar con `limit` y `offset` (es el `history.py` actual: si el catálogo
  cambia entre páginas se pierden o repiten eventos sin aviso); una sola petición anual (cabe
  hoy, pero el enunciado pide meses y no escala a todas las magnitudes).
- **`producer/app/history.py` se retira**: lo sustituye este programa; escribía en `db/seeds/`,
  dentro de Git.

## R9. Dónde se ejecuta la carga

- **Decisión**: un servicio de Compose `catalog-loader` bajo el perfil `tools`, con la imagen
  del productor, `./data` montado con escritura y el programa de carga como punto de entrada. Se
  lanza con `docker compose run --rm catalog-loader [argumentos]`. El servicio `producer` sigue
  montando `./data` en solo lectura.
- **Razón**: `docker compose up --build -d` sigue arrancando exactamente cinco servicios; la
  carga solo existe cuando se pide (FR-018). Kafka y PostgreSQL no publican puertos, así que la
  carga tiene que ejecutarse dentro de la red.
- **Permisos en Linux**: la imagen usa un usuario sin privilegios (uid 10001) que no puede
  escribir en un directorio del equipo propiedad de otro usuario. El servicio toma el usuario de
  `LOADER_UID` y `LOADER_GID` (por defecto 0, como el contenedor de pruebas); en Linux se
  exportan con el usuario propio para que los ficheros no queden como `root`. **Pendiente de
  comprobar al implementar en el equipo Linux.**
- **Alternativas**: ejecutarlo fuera de Docker (no alcanza Kafka ni PostgreSQL); un sexto
  servicio permanente (rompe el arranque de cinco servicios).

## R10. Detección y recuperación de huecos

- **Decisión**: los huecos se calculan a partir del propio registro de extracciones, sin estado
  nuevo: un hueco es el intervalo entre dos consultas correctas consecutivas al feed separadas
  por más de 24 horas, desde la primera (menos un margen) hasta 24 horas antes de la segunda
  (más el margen). Margen: `GAP_MARGIN_MINUTES`, 60 por defecto, porque USGS publica eventos con
  retraso (mediana 3,5 min, pero con casos de horas). Un hueco está recuperado cuando las
  consultas correctas con propósito `gap_recovery` hechas después de él cubren todo el intervalo.
  - Al arrancar, el productor compara la última consulta correcta con la hora actual; si hay
    hueco, escribe un aviso con la orden exacta y sigue con el feed.
  - `catalog-loader --gaps` lista los huecos pendientes en cualquier momento (FR-031).
  - La recuperación es la misma carga con `--purpose gap_recovery`, sin magnitud mínima ni tipo.
- **Razón**: el aviso del arranque desaparece del log, pero el registro de extracciones se
  conserva para siempre: la información del hueco no se pierde aunque el feed lleve días
  funcionando otra vez. No requiere cambios en el modelo. El índice parcial de la spec 002 sobre
  las consultas correctas al feed sirve esta consulta.
- **Alternativas**: tabla de huecos pendientes (cambio de modelo); recuperación automática
  (descartada por la persona autora el 2026-11-15: el enunciado solo pide explicarla).

## R11. Purga de originales

- **Decisión**: el productor llama a `core.purge_raw_payload(RAW_PAYLOAD_RETENTION_DAYS)` al
  arrancar y después cada 24 horas, entre ciclos, y registra en el log cuántos eliminó. FR-033
  acepta el log como constancia; el número y el tamaño observados se guardan en la evidencia.
- **Volumen estimado**: el feed cambia casi cada minuto; 17 kB comprimidos × 1.440 consultas ×
  7 días ≈ 175 MB como máximo, dentro de lo previsto en la spec 002.
- **Alternativas**: purgar en cada ciclo (1.440 borrados diarios sin beneficio); un servicio
  aparte (un sexto contenedor).

## R12. Salud del productor

- **Decisión**: el latido se actualiza al terminar cada ciclo que queda registrado, también si
  la fuente falló. El productor solo deja de estar sano si no puede registrar el ciclo (base o
  broker caídos) o se queda bloqueado.
- **Razón**: una caída de USGS no es un fallo del servicio; la antigüedad de `last_ingestion` ya
  la refleja (FAQ 31). Hoy un fallo de la fuente dejaría `docker compose up --wait` sin terminar.
- **Sigue cumpliendo la spec 002**: «latido tras cada ciclo correcto» pasa a entenderse como
  ciclo completado y registrado; se anota en el contrato de ejecución de esta spec y se
  actualiza la frase correspondiente en el de la spec 002 y en el README.

## R13. Fuente simulada para probar fallos

- **Decisión**: las direcciones del feed y del catálogo son configurables (`USGS_FEED_URL`,
  `USGS_CATALOG_URL`). Un servidor mínimo en `tests/support/usgs_stub.py` (biblioteca estándar)
  responde según un guion: 429 con `Retry-After`, 503, espera hasta agotar el tiempo, JSON
  ilegible, estructura no válida, 304 y respuestas correctas con elementos de otros tipos. Las
  pruebas automáticas lo arrancan en un hilo; para la evidencia con el sistema real se añade a
  `compose.dev.yaml` como servicio `usgs-stub` y se arranca un productor apuntando a él.
- **Razón**: FR-037 y SC-008 exigen probar los fallos sin depender de que USGS falle.

## R14. Descripción de la respuesta de la fuente

- **Decisión**: un programa `tests/analysis/source_profile.py` lee los originales guardados
  (cuerpos del feed en `core.raw_payload` y ficheros del catálogo) y las extracciones, y escribe
  `docs/evidence/003/source-profile.md`: por cada campo, tipos observados, porcentaje de nulos y
  rango; frecuencia real de cambio del feed; errores registrados; latencia de las consultas
  (`duration_ms`) y retraso de publicación (`updated − time` e ingesta − ocurrencia). La memoria
  resume esa evidencia y añade unidades y significado.
- **Razón**: FR-036a y el nivel sobresaliente de «Extracción» (carga con análisis de tipos)
  piden datos observados, no una copia de la documentación de USGS.

## R15. Modelo de datos

- **Decisión**: ningún cambio en el modelo de la spec 002 (FR-035). **Verificado** contra
  `db/sql/`: `core.extraction` tiene todos los campos de FR-001 a FR-003 y `request_params`
  para los del catálogo; `core.raw_payload` admite cuerpos (`gzip`) y ficheros (`file`);
  `core.excluded_event` referencia la extracción; `observatory_writer` puede insertar y
  actualizar en las tres y ejecutar `core.purge_raw_payload`; el índice de `last_ingestion` ya
  existe.
- **Único uso nuevo**: `extraction.error_detail` también describe elementos no identificables en
  consultas correctas (R5), y `request_params.endpoint` distingue recuentos de descargas (R8).
  Ambos se documentan en el diccionario de datos.

## R16. Configuración nueva

| Variable | Usada por | Por defecto |
|---|---|---|
| `USGS_CATALOG_URL` | productor, carga | `https://earthquake.usgs.gov/fdsnws/event/1` |
| `USGS_TIMEOUT_SECONDS` | productor, carga | 30 |
| `USGS_MAX_ATTEMPTS` | productor, carga | 4 |
| `USGS_USER_AGENT` | productor, carga | `seismic-observatory/1.0` (sin datos personales) |
| `GAP_MARGIN_MINUTES` | productor, carga | 60 |
| `DATA_DIR` | carga | `/data` |
| `LOADER_UID`, `LOADER_GID` | Compose (`catalog-loader`) | 0 |

`USGS_FEED_URL`, `PRODUCER_INTERVAL_SECONDS` y `RAW_PAYLOAD_RETENTION_DAYS` ya existen.

## R17. Pruebas

- **Unitarias** (`tests/unit`): cliente HTTP contra la fuente simulada (reintentos,
  `Retry-After`, tiempo agotado, clasificación de resultados), huella canónica, clasificación de
  elementos, planificación y subdivisión de intervalos con recuentos simulados, cálculo de
  huecos y de su cobertura.
- **Con base real** (`tests/db`): un ciclo completo del feed y una carga del catálogo contra
  `observatory_test`, con la fuente simulada y un broker simulado: extracción, original único,
  exclusiones, `published_count`, 304, repetición y reanudación.
- **Con el sistema real** ([quickstart.md](quickstart.md)): una hora de feed, carga de 2025 y de
  2026, interrupción y reanudación, hueco de 36 horas, purga y fallos de la fuente.
