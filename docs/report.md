# Memoria del Observatorio Sísmico

Este documento reúne las decisiones de diseño del observatorio y su justificación. Se completa
funcionalidad a funcionalidad; esta versión contiene los apartados de la plataforma y el modelo
de datos (spec 002). Las cifras citadas proceden de mediciones guardadas en
[docs/evidence/002/](evidence/002/).

## Alcance y decisiones

**Datos que el sistema debe guardar.** El enunciado exige el histórico mundial de 2025 con
magnitud ≥ 4 y tipo terremoto (unos 16.000 eventos) y el feed en vivo de USGS de las últimas
24 horas, consultado cada minuto (unos 200 eventos nuevos y hasta 10.080 consultas por semana).
El histórico de 2025 es dato real: se guarda en el esquema `core`, distinguido del feed por su
procedencia (`source = 'usgs_catalog'`), y no en el de reproducción. El modelo no impide cargar
el catálogo completo desde 1900: la dimensión de fecha empieza ese año y las tablas no tienen
límites de volumen; la carga ampliada queda para una funcionalidad posterior.

**Decisiones propias del modelo.**

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Esquemas `core` (real) y `replay` (reproducción) con la misma plantilla de tablas | Una columna «origen» en tablas compartidas | El aislamiento queda garantizado por la estructura: una consulta o un borrado de `replay` no puede tocar `core` |
| Regla de versiones en la función `apply_event_version` | Dos sentencias desde Python | La regla vive junto a sus restricciones, se prueba con SQL y devuelve el resultado que se cuenta (`new`, `revised`, `stale`, `duplicate`) |
| País nulo cuando el punto no cae en ningún polígono | Fila ficticia «Sin país asignado» | No se inventa una entidad en la dimensión; el texto lo pone la presentación |
| Magnitud y profundidad anulables, sin mínimo | Rechazar nulos y negativos | El principio III obliga a conservar o señalar; una magnitud negativa o una profundidad sobre el nivel del mar son reales |
| Tres roles de base de datos (propietario, escritor, lector) | Un único usuario | La API, única pieza expuesta a Internet, no puede modificar datos aunque tenga un fallo |
| Registro de cada mensaje procesado (`message_log`) | Contar en los logs | Da los denominadores de calidad con SQL; no es fuente de recuentos de terremotos |
| Originales del feed comprimidos, una vez por huella y durante 7 días | Guardar todos los cuerpos sin límite | Con hasta 10.080 consultas por semana, 30 días superarían 1,5 GB; 7 días quedan por debajo de 400 MB |
| Índices secundarios solo si su consulta es al menos 2 veces más rápida | Indexar todo de antemano | Cada índice cuesta espacio y escrituras; se conserva el que demuestra su beneficio |

**Material reutilizado frente a desarrollado.**

| Reutilizado | Desarrollado en este proyecto |
|---|---|
| Catálogo de países Natural Earth entregado (`frontend/public/datos/paises.geojson`, 177 entidades) | Modelo de datos completo (`db/sql/`), función de versiones, reglas de esquema y privilegios |
| Imágenes oficiales de PostgreSQL 16.4, Kafka 7.7.1 (Confluent), Python 3.11 y ngrok | `compose.yaml`, comprobaciones de salud, reintentos y creación de topics (`common/`) |
| Bibliotecas: aiokafka, asyncpg, FastAPI, GeoPandas, Shapely | Pruebas del modelo (`tests/db`), medición de índices (`tests/benchmark`) y arranques (`tests/startup`) |
| Feed y API de catálogo de USGS como fuente de datos | Adaptación de productor, consumidor y API al modelo nuevo |

## Fuentes y extracción

Esta sección describe lo que USGS devuelve de verdad, cómo se registra cada consulta y qué
limitaciones tiene la extracción. Las cifras proceden de respuestas reales guardadas por el
sistema; el perfil completo, campo a campo, está en
[source-profile.md](evidence/003/source-profile.md), generado por
[tests/analysis/source_profile.py](../tests/analysis/source_profile.py).

### Fuentes

| Fuente | Acceso | Qué devuelve | Frecuencia |
|---|---|---|---|
| Feed `all_day.geojson` | `GET https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson` | Ventana móvil de las últimas 24 horas, completa en cada respuesta | Cada 60 s (`PRODUCER_INTERVAL_SECONDS`) |
| Catálogo FDSN | `GET https://earthquake.usgs.gov/fdsnws/event/1/count` y `/query` | Eventos de un intervalo `[starttime, endtime)` con filtros de magnitud y tipo; como máximo 20.000 por respuesta | A demanda (`catalog-loader`) |
| Natural Earth | `frontend/public/datos/paises.geojson` (copia entregada) | 177 entidades con polígonos y atributos | Una vez, al crear la base |

### Respuesta del feed

Un `FeatureCollection` GeoJSON con `metadata` (`generated`, `count`, `status`, `api`…), `bbox` y
`features`. Medido el 2026-11-15 sobre 37 respuestas distintas: unos 185–192 elementos, todos de
tipo `earthquake` y geometría `Point` con 3 coordenadas; 137 kB sin comprimir y 17 kB con gzip;
servidos con una mediana de 97 ms. La respuesta lleva `Last-Modified` y `Cache-Control: max-age=60`, sin
`ETag`. La petición condicional (`If-Modified-Since`) obtuvo 3 respuestas 304 en una hora de
funcionamiento; el resto de minutos USGS había regenerado el feed, aunque solo cambiaron los
eventos de 17 de esas 60 respuestas.

Campos que usa el sistema:

| Campo | Tipo observado | Unidad | Significado | Ausencias observadas |
|---|---|---|---|---|
| `id` | texto | — | Identificador del evento en USGS | Nunca falta |
| `properties.time` | entero | ms Unix, UTC | Momento de ocurrencia | Nunca falta |
| `properties.updated` | entero | ms Unix, UTC | Última actualización en USGS; identidad de la versión | Nunca falta |
| `properties.mag` | decimal o entero | adimensional | Magnitud, en la escala de `magType`; hay valores negativos (−0,02) | Ninguna en el periodo observado; el modelo admite nulos |
| `properties.magType` | texto | — | Tipo de magnitud (ml, md, mb, mw…) | Ninguna en el periodo observado |
| `properties.type` | texto | — | Tipo de evento; solo `earthquake` se publica | Nunca falta |
| `properties.place` | texto | — | Descripción libre del lugar | Ninguna en el feed observado; 1 nula entre los 32.655 eventos del catálogo |
| `geometry.type` | texto | — | Siempre `Point` | Nunca falta |
| `geometry.coordinates[0]`, `[1]` | decimal | grados WGS84 | Longitud y latitud | Nunca faltan |
| `geometry.coordinates[2]` | decimal o entero | km | Profundidad; negativa si el foco está sobre el nivel del mar (mínimo observado −2,74) | Nunca falta |

Campos opcionales que el sistema conserva en el original pero no usa: `alert` (nulo en el
99 %), `mmi` (96 %), `felt` y `cdi` (94 %) y `tz` (100 %). El retraso entre ocurrencia y última
actualización (`updated − time`) tiene en el feed una mediana de 3,5 min, pero un percentil 95
de unas 12 horas y casos de más de 20 horas: un evento puede revisarse muchas veces mientras
está en el feed, y por eso cada versión se publica y se conserva. En el catálogo la mediana es
de unos 76 días: lo que se descarga ya está revisado. El retraso de ingesta de los eventos
ocurridos con el sistema en marcha (desde la ocurrencia hasta su primera escritura en la base)
tiene una mediana de 3,2 min y un percentil 95 de 4,1 min, sobre 9 eventos.

### Respuesta del catálogo

El mismo formato GeoJSON, con `metadata.count` igual al número de elementos. `/count` devuelve
`{"count": N, "maxAllowed": 20000}` en 0,3–1,4 s. Comprobado con peticiones reales el
2026-11-15:

- una consulta que excede el máximo devuelve **HTTP 400** («N matching events exceeds search
  limit of 20000»); USGS no trunca si no se le pide un `limit`, y el sistema no lo pide nunca;
- los límites son `[starttime, endtime)`: un evento justo en el límite pertenece solo al
  intervalo que empieza en él. El enunciado advierte de que pueden incluirse ambos extremos, así
  que se deduplica igualmente por identificador;
- ningún mes de 2025 ni de 2026 supera el máximo con magnitud ≥ 4 (el mayor, julio de 2025,
  tiene 2.684), ni siquiera con todas las magnitudes (septiembre de 2026: 11.740).

### Cómo se carga

- **Feed** (`producer`): cada minuto, una consulta. Se registra siempre en `core.extraction`
  (resultado, código HTTP, intentos, duración, `metadata.generated` y el reparto recibidos =
  terremotos + excluidos); el original se guarda comprimido una vez por contenido distinto; los
  elementos de otro tipo se guardan en `core.excluded_event`; solo se publican las versiones con
  `updated` posterior a la ya publicada, y se marcan tras la confirmación de Kafka.
- **Catálogo** (`docker compose run --rm catalog-loader`): por meses, primero el recuento y
  después la descarga, que debe traer exactamente lo declarado; si un intervalo excede el
  máximo se divide por mitades. Cada respuesta se guarda sin modificar en `data/usgs/catalog/`
  con su huella en el nombre, y la base registra la huella y la ruta. Los eventos se publican
  por el topic `earthquakes.catalog` y entran en `core` con la misma regla de versiones que el
  feed. Un intervalo cuyo fichero existe con la huella registrada no se vuelve a descargar
  («descarga una vez y reutiliza», enunciado §4.2), así que repetir la orden continúa una carga
  interrumpida y no publica nada dos veces.

### Registro de procedencia

| Conjunto | Fuente | Periodo y filtros | Extracción | Consultas | Registros |
|---|---|---|---|---|---|
| Histórico obligatorio | Catálogo FDSN | 2025-01-01 a 2026-01-01, mundial, magnitud ≥ 4, `eventtype=earthquake` | 2026-11-15, 11:40–11:43 UTC | 12 descargas mensuales y sus recuentos, más el recuento del año | 18.302 (declarados por USGS: 18.302) |
| Ampliación 2026 | Catálogo FDSN | 2026-01-01 a 2026-11-15, mismo filtro | 2026-11-15, 11:51–11:53 UTC | 11 descargas y sus recuentos | 14.225 (declarados: 14.225) |
| Reciente | Feed `all_day.geojson` | Últimas 24 h, todas las magnitudes, todos los tipos (solo se publican terremotos) | Continua desde 2026-11-15 11:31 UTC | Una por minuto | Variable; ver `core.extraction` |

Las consultas, sus parámetros y sus recuentos están en `core.extraction`
(`request_params.endpoint` distingue recuentos y descargas), y los resúmenes de cada carga en
`data/usgs/catalog/summary-*.json`. Evidencia: [catalog-load.md](evidence/003/catalog-load.md) y
[catalog-load-2026.md](evidence/003/catalog-load-2026.md).

**Periodos con distinto filtro.** El espacio real contiene 2025 y 2026 hasta el 15 de noviembre
con magnitud ≥ 4, y a partir de la puesta en marcha del feed, todas las magnitudes. Cualquier
comparación entre periodos debe usar el mismo filtro (magnitud ≥ 4 y tipo terremoto).

### Originales y retención

- La huella de una respuesta del feed se calcula sobre la lista de eventos en JSON canónico, no
  sobre la respuesta completa: `metadata.generated` cambia en cada regeneración aunque los
  eventos sean los mismos. Dos respuestas con los mismos eventos ocupan una sola fila.
- Los cuerpos del feed se purgan cuando llevan más de 7 días sin observarse
  (`RAW_PAYLOAD_RETENTION_DAYS`); el productor lo hace al arrancar y cada 24 horas, y anota en su
  log cuántos eliminó. Las extracciones y las referencias a ficheros del catálogo no caducan.
- Estimación: unos 17 kB comprimidos por contenido distinto y, como mucho, uno por minuto, es
  decir, menos de 175 MB en 7 días. El tamaño medido está en
  [retention.md](evidence/003/retention.md).
- Los ficheros del catálogo (13 MB para 2025) están fuera de Git, en `data/`; la versión
  original de cada evento se conserva además en `event_version.payload`.

### Fallos de la fuente

| Fallo | Qué hace el sistema |
|---|---|
| Tiempo agotado, sin conexión, HTTP 429 o 5xx | Hasta 4 intentos con espera de 1, 2 y 4 s, o la de `Retry-After` si es mayor; si `Retry-After` supera 120 s no se reintenta en ese ciclo y no se vuelve a consultar antes del plazo |
| Otro 4xx | No se reintenta |
| Respuesta que no es JSON (también `NaN` o `Infinity`, que no son JSON) | Resultado `invalid_json`; se guarda lo recibido |
| JSON sin la estructura `FeatureCollection` | Resultado `invalid_structure`; se guarda lo recibido |

En todos los casos la consulta queda registrada con su resultado, intentos y detalle; no se
publica ni se borra nada, y el ciclo siguiente lo vuelve a intentar sin intervención. Un fallo
de USGS no vuelve `unhealthy` al productor: se ve en la antigüedad de la última ingesta
(`last_ingestion`, la última consulta al feed con resultado `ok` o `not_modified`). Si la base
falla después de que USGS respondiera, el resultado se conserva en memoria y se registra al
volver la base, antes de consultar otra vez. Evidencia:
[source-failures.md](evidence/003/source-failures.md).

### Recuperación de huecos

El feed solo cubre 24 horas. Si la ingesta se para más tiempo, al arrancar el productor escribe
en su log el periodo no cubierto y la orden exacta para recuperarlo, y sigue con el feed:

```text
Ingestion gap detected: last successful feed request at <instante>; events between <inicio> and
<fin> are not covered by the feed. Recover with: docker compose run --rm catalog-loader
--purpose gap_recovery --start <inicio> --end <fin>
```

El periodo va desde la última consulta correcta hasta 24 horas antes de la siguiente, con un
margen de 60 minutos a cada lado para los eventos que USGS publica con retraso. La recuperación
usa la carga del catálogo con todas las magnitudes y todos los tipos, como el feed, y registra
sus consultas con el propósito `gap_recovery`. Los huecos se calculan siempre desde
`core.extraction`, así que `catalog-loader --gaps` los lista, pendientes o recuperados, aunque el
aviso ya no esté en el log. No se automatiza: el enunciado pide explicar cómo recuperar el
hueco y la recuperación manual se puede demostrar sin añadir complejidad. Evidencia:
[gap-recovery.md](evidence/003/gap-recovery.md).

### Limitaciones del alcance

- **Instantánea del catálogo.** El histórico es el catálogo tal como estaba en la fecha de
  extracción; un evento revisado después solo se actualiza al repetir la carga.
- **Eventos fuera del feed.** No se reconcilian los eventos que USGS elimina, fusiona o revisa
  cuando ya han salido de la ventana de 24 horas. Que un evento deje de aparecer en el feed no
  significa que se haya eliminado, y nunca se borra nada.
- **Hueco recuperado tarde.** La recuperación consulta el catálogo cuando se ejecuta, no como
  estaba durante la parada.
- **Consulta sin registro.** Si el productor se reinicia justo mientras tiene una respuesta
  pendiente de registrar porque la base estaba caída, esa consulta se pierde. Es el único caso.
- **Cuarentena heredada.** Hasta la spec 004 el consumidor envía a cuarentena los eventos sin
  magnitud; en una recuperación con todas las magnitudes puede haber más publicados que
  almacenados, y la diferencia está en `core.quarantine`.

## Calidad de los datos

### Conjunto analizado

- **Fuente y periodo**: feed de USGS (desde el 2026-11-15 11:31 UTC) y catálogo histórico de USGS
  (2025 y 2026 hasta el 15-11, magnitud ≥ 4), tal como están en `core` el **2026-11-16**.
- **Denominadores** (siempre explícitos): **33.112 mensajes recibidos** (`message_log`,
  `attempt = 0`), **33.112 versiones distintas** (`event_version`) y **32.978 terremotos
  actuales** (`event_current`; 445 del feed y 32.533 del catálogo).
- **Sin sintéticos**: todas las consultas excluyen los casos de prueba dañados a propósito
  (1.031 mensajes, ver «Casos sintéticos»). Las consultas están en
  [db/queries/quality.sql](../db/queries/quality.sql) y se ejecutan con
  `docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /queries/quality.sql'`;
  entre corchetes va el nombre de cada una. Evidencia:
  [spatial-and-counts.md](evidence/004/spatial-and-counts.md).
- Los problemas pueden solaparse: **no se suman incidencias** entre filas para obtener un total
  de registros «malos». Cada fila usa su propio denominador.

### Reglas del consumidor y decisiones

Cada regla tiene un código estable, una dimensión y una justificación en el catálogo
([contracts/rules-catalog.md](../specs/004-consumer-quality/contracts/rules-catalog.md));
`consumer/app/rules.py` es su única implementación y una prueba comprueba que coinciden. Solo
va a cuarentena lo que **no puede tratarse**: JSON ilegible, sin identificador, sin tiempo o sin
versión legibles, geometría que no es un punto, coordenadas no numéricas o fuera de rango, o una
versión que el modelo rechaza. Todo lo demás se conserva, con una marca si es anómalo.

| Decisión | Por qué |
|---|---|
| No sustituir la magnitud o la profundidad ausentes por cero | Introduciríamos un valor que la fuente no da y falsearíamos medias y mínimos; se conservan nulas y se excluyen de los cálculos que las necesitan, informando del denominador |
| No rechazar la magnitud negativa | Las escalas locales dan valores negativos (el mínimo observado es −0,02); no es un error por sí misma y **no lleva marca** |
| Marcar, no rechazar, la profundidad negativa | Es un foco sobre el nivel del mar (mínimo observado −2,74 km); se señala con `negative_depth` para poder estudiarla |
| Marcar los valores fuera de [−2, 10] de magnitud o más de 800 km | Un valor raro se señala; la medición física no se puede verificar desde los datos (ver exactitud) |
| Retirar el rechazo por antigüedad (7 días) | Impedía cargar el histórico y recuperar huecos por el mismo camino; una versión antigua no es un defecto |
| Retirar el rechazo por tiempo futuro | Un reloj desajustado no invalida el evento; pasa a la marca `future_time` (más de 5 min tras la recepción) |
| Retirar `duplicate_id` | Nunca se aplicaba y la repetición la resuelve la regla de versiones del modelo |
| Dejar al modelo como última barrera | Si rechaza una versión (p. ej. fecha anterior a 1900), va a cuarentena con `model_constraint_violation` y el detalle del error; no se replican sus restricciones |

### Antes y después

| Problema | Antes (reglas heredadas) | Acción | Después |
|---|---|---|---|
| Magnitud fuera de 0–10 (incluida la negativa) | 2 mensajes del mismo evento en cuarentena (`magnitude_out_of_range`), fuera del análisis | Regla retirada; reprocesado de la cuarentena | 2 recuperados (`recovered_new`, `recovered_revised`); el evento tiene magnitud −0,02 y país `USA`. Cuarentena real: 2 filas conservadas con su resultado |
| Magnitud nula | Habría ido a cuarentena (`magnitude_null`) | Se conserva nula | Probado con el caso sintético `null_magnitude`: queda en el estado actual con `magnitude` nula; en los datos reales hay 0 nulos |
| Profundidad negativa | 5 eventos sin señalar | Marca `negative_depth` desde que rige la regla | Los 5 ya guardados conservan el valor y **no se re-marcan** (se guardaron antes); se cuentan por la columna; los nuevos llevan la marca |
| País por orden de polígonos | `matches.iloc[0]`: el orden decidía en una frontera | Orden por `ADM0_A3` y marca `ambiguous_country` | Recalculados los 32.977 eventos reales: **0 cambian de país**, 0 ambiguos |
| Versiones duplicadas | La clave primaria ya las impedía | Sin cambios | 0 [duplicated-versions] |

### Calidad por dimensión

**Completitud** — sobre 32.978 terremotos actuales [completeness]:

| Campo | Informado | Tratamiento de la ausencia |
|---|---|---|
| Magnitud | 32.978 (100 %) | Nula = ND, excluida de medias y filtros por magnitud, contada aparte; el panel debe indicar cuántas excluye |
| Tipo de magnitud | 100 % | Nulo |
| Profundidad | 100 % | Nula = ND |
| Lugar | 100 % | Nulo |
| País | 7.624 (23,12 %) | Nulo = «Sin país asignado»; permanece en el análisis |

*Acción*: ninguna sobre los datos reales (no hay ausencias de magnitud, profundidad, tipo ni lugar);
el comportamiento ante ausencias está probado con casos sintéticos (magnitud, profundidad y tipo
nulos o no numéricos). *Limitación*: 25.354 eventos sin país (el 76,9 %) son sobre todo marinos y
costas recortadas por la escala 1:110.000.000; el catálogo no permite distinguir un evento marino
de uno en tierra mal cubierto.

**Unicidad** — [versions-vs-messages] **33.112 versiones distintas para 33.112 mensajes**: ninguna
repetición exacta en los datos reales. [duplicated-versions] 0 versiones duplicadas y
[current-uniqueness] 0 identificadores repetidos en el estado actual: lo garantizan las claves
primarias. 135 revisiones de 91 eventos (versiones que no son la actual). *Limitación*: la carga
de 2025 y 2026 trae una instantánea sin sus revisiones pasadas (enunciado §4.2); las repeticiones
solo aparecen cuando el feed reenvía una versión. La regla `duplicate` se prueba en `tests/db`.

**Validez** — [invalid-coordinates] 0 terremotos actuales con coordenadas fuera de rango;
[quarantined-messages] 2 mensajes en cuarentena real (ya reprocesados). Rangos observados:
magnitud −0,02 a 8,8, profundidad −2,74 a 683,6 km, sin valores fuera del rango plausible
[events-by-flag]. Todas las coordenadas son finitas y la geometría es siempre un `Point` con tres
valores (perfil en [source-profile.md](evidence/003/source-profile.md)). *Acción*: coordenadas
imposibles → cuarentena con motivo y original; valores raros → marca. *Limitación*: el rango
plausible es una convención documentada, no una verdad física.

**Consistencia** — [updated-before-event] 0 versiones con `updated_at` anterior a `event_time`;
[country-missing-entity] 0 países que no existan en la dimensión (`ADM0_A3` único, comprobado al
arrancar). La secuencia de revisiones queda ordenada por la regla de versiones (`new`, `revised`,
`stale`, `duplicate`): [messages-by-outcome] 32.976 nuevos, 134 revisados y 2 rechazados, y
[received-check] **recibidos = suma de resultados, diferencia 0**. Unidades coherentes: magnitud
adimensional, profundidad en km, coordenadas en grados WGS84, tiempos en UTC.

**Actualidad** — distingue tres tiempos: ocurrencia (`event_time`), actualización en USGS
(`updated_at`) y ingesta (`first_ingested_at`), todos en UTC [delays-updated-minutes,
delays-ingested-minutes]:

| Medida | Mediana | Percentil 95 | Lectura |
|---|---|---|---|
| Ocurrencia → actualización en USGS, catálogo | ≈ 76 días | ≈ 91 días | Lo descargado ya está revisado |
| Ocurrencia → actualización en USGS, feed | 3,5 min | ≈ 12 h | Una revisión antigua aumenta la diferencia; no es un retraso |
| Ocurrencia → ingesta, eventos con el productor en marcha | 3,2 min | 4,1 min | Mide el sistema (9 eventos, [source-profile.md](evidence/003/source-profile.md)) |
| Ocurrencia → ingesta, todos los eventos | ≈ 364 días | ≈ 648 días | Sin interés: está dominado por la carga histórica |

*Limitación*: los eventos que ya estaban en la ventana de 24 h al arrancar el feed y los
ocurridos durante una parada tienen un retraso que mide la parada, no la ingesta; se tratan
aparte.

**Exactitud** — Se puede contrastar: tipos y unidades, rangos, finitud, coherencia temporal y
que el país obtenido exista en la dimensión. **No se puede contrastar** que la magnitud o la
profundidad sean las físicas: comprobar que un valor es numérico y plausible no demuestra que
sea exacto, y no hay una segunda fuente independiente en el proyecto. Tampoco la asignación de
país tiene precisión cartográfica: los límites están simplificados (escala 1:110.000.000), y un
punto sobre una frontera recibe la entidad de `ADM0_A3` menor con la marca `ambiguous_country`.
Las revisiones de USGS (`status` automático o revisado) pueden cambiar los valores; el sistema
conserva todas las versiones.

### Integración espacial

El país se obtiene con **punto en polígono** (longitud y latitud, EPSG:4326) sobre la copia
entregada de Natural Earth, nunca del texto de `place` (probado con un evento cuyo `place` dice
«Madrid» en el Pacífico: queda sin país). Al arrancar, el consumidor comprueba que `ADM0_A3` es
único y que todas las entidades existen en `core.dim_country`, y se detiene con un mensaje claro
si no. Un punto en varias entidades o sobre una frontera recibe la de `ADM0_A3` menor en orden
alfabético y la marca `ambiguous_country`; el resultado es siempre el mismo. Sin polígono →
país nulo, «Sin país asignado», sin error y dentro de los totales.

### Reprocesar la cuarentena

Los mensajes rechazados por reglas que ya no existen se recuperan con
`docker compose run --rm quality-reprocess` (ver [reprocess.md](../specs/004-consumer-quality/contracts/reprocess.md)):
aplica las reglas vigentes a cada fila pendiente, en el espacio de su topic, escribe una fila
`attempt = 1` en el registro de mensajes junto a la original y marca la fila de cuarentena con la
fecha y el resultado. Es idempotente y no borra nada. Evidencia:
[reprocess.md](evidence/004/reprocess.md).

### Casos sintéticos

Para probar el consumidor sin inventar errores en los datos reales hay 30 casos dañados a
propósito (`tests/synthetic/cases.py`) y un lote de 1.000 mensajes válidos. Llevan el prefijo
reservado `synthetic-` en el identificador (y como clave de Kafka), la marca `synthetic` en el
evento y su versión, e `is_synthetic` en la cuarentena. Todas las consultas de esta sección los
excluyen; la variante `-synthetic-only` de cada una los cuenta aparte: 1.013 eventos sintéticos,
16 en cuarentena y 2 exclusiones. Evidencia: [acceptance.md](evidence/004/acceptance.md) y
[restart.md](evidence/004/restart.md).

### Limitaciones

- Las marcas de calidad solo se asignan al procesar un mensaje: los eventos guardados antes de
  esta regla (2025 y el feed anterior) no están re-marcados; las consultas usan las columnas
  para cifras como la profundidad negativa.
- Ninguna comprobación demuestra la exactitud física de una magnitud.
- El feed lleva solo unas horas de datos reales: los porcentajes del feed son frágiles y las cifras
  del feed crecen con el tiempo (las de esta sección son del 2026-11-16).
- Los eventos sin magnitud no aparecen en el histórico de 2025 y 2026 porque se cargó con
  magnitud ≥ 4; la recuperación de un hueco, que trae todas las magnitudes, sí los puede traer.

## Reproducción histórica

Esta sección documenta la reproducción acelerada de una selección histórica (spec 005). Sirve para
demostrar el sistema con actividad aunque no ocurra ningún terremoto durante la defensa (enunciado
§11, prueba «Reproducción histórica»; FAQ 32), sin mezclarla nunca con los datos reales (principio VI
de la constitución). El etiquetado «REPRODUCCIÓN» en la API y en el panel corresponde a las specs 006
y 007; aquí se garantiza la parte de datos: circulación por Kafka, aislamiento e identificabilidad.

### Qué es y qué no es

| Es | No es |
|---|---|
| Una orden (`replay`) que publica en `earthquakes.replay` una selección de lo **ya descargado** en `data/usgs/catalog/` | Una consulta a USGS: no hay ninguna durante la reproducción |
| Un flujo por Kafka → mismo consumidor → esquema `replay` | Un camino aparte con código propio: el consumidor es el de la spec 004 |
| Una demostración repetible (`reset` y repetir) | Una prueba de carga: las cifras de cadencia son de conformidad, no de rendimiento |

### Diseño

```text
data/usgs/catalog/*.geojson ──► selección (periodo, magnitud mínima, recuadro opcional)
        │                         · verifica huella contra core.raw_payload (principio V)
        │                         · registra la consulta en core.extraction (purpose = replay_selection)
        ▼
 orden `replay start`  ──► Kafka earthquakes.replay (mode "replay", clave = id del evento,
        │                  time y updated originales, replayed_at nuevo)
        ▼
 consumidor (spec 004) ──► esquema replay  (core no se toca)
```

- **Selección**: sale de los ficheros descargados y se ordena por tiempo de ocurrencia. Falla sin
  publicar nada si un fichero no coincide con su huella, si el periodo no está cubierto por cargas
  registradas o si la magnitud mínima pedida es menor que la de la carga (una selección que se quedara
  corta en silencio daría datos que parecen reales). Un evento repetido entre ficheros se publica una
  vez con su `updated` mayor. Las magnitudes nulas no cumplen un filtro de magnitud mínima y se cuentan.
- **Zona**: recuadro geográfico opcional (`--bbox=min_lon,min_lat,max_lon,max_lat`), sin cruce del
  antimeridiano. No es un filtro por país: el país lo asigna después el consumidor por punto en polígono
  (principio IV), y asignarlo en la selección habría duplicado esa integración.
- **Cadencia**: `--rate` (eventos por segundo) y `--speedup` opcional sobre el tiempo original; con
  ambos, la cadencia nunca supera la velocidad indicada. Los plazos son absolutos para que el retraso del
  envío no se acumule, y tras una pausa se rebasan para no emitir en ráfaga.
- **Control**: `pause`, `resume`, `stop`, `status` y `reset` mediante un fichero en `data/replay/`
  (sin puertos ni servicio nuevo). Solo una reproducción activa a la vez, con un bloqueo asesor de
  PostgreSQL que se libera solo si el proceso muere.
- **Tiempo**: `time` y `updated` viajan como los publicó USGS; se añade `replayed_at` (instante real de
  la publicación). Nunca se alteran fechas para que parezcan recientes.
- **Mensaje y modelo**: sin cambios de modelo. Un único cambio en el consumidor de la spec 004: usa el
  `replayed_at` que trae el mensaje (antes ponía la hora de lectura), para que el valor no cambie si el
  consumidor se reinicia y relee.

### Aislamiento

Los eventos reproducidos solo terminan en el esquema `replay`, que es lo que decide el topic de origen.
Un mismo identificador puede existir en `core` y en `replay` con valores distintos sin interferir. La
comprobación (`replay snapshot` y `replay compare`) toma, para cada tabla de `core` descubierta en el
catálogo de PostgreSQL, el recuento y la suma de `hashtextextended` de cada fila, y los compara antes y
después. La única diferencia admitida es la fila que cada selección deja en `core.extraction`
(propósito `replay_selection`), que es la constancia que exige la spec y que la comparación cuenta
aparte. Debe hacerse con el productor en vivo parado, porque el feed real escribe en `core` por su
cuenta.

Desde la base, un dato es de reproducción si está en el esquema `replay`, si `replayed_at` no es nulo
(la restricción del modelo lo obliga en `replay` y lo prohíbe en `core`) y si su `kafka_topic` es el de
reproducción. El modo `"replay"` viaja en el mensaje de Kafka; el modelo no guarda el mensaje completo
(solo el `Feature` original), por lo que no se usa como criterio desde la base.

### Casos sintéticos

Siete mensajes, cinco casos, con fechas fijas y la convención de la spec 004 (`synthetic-replay-…`,
marca `synthetic`): primera versión, repetición exacta, revisión, versión antigua tardía y un mensaje
que va a cuarentena. Se publican con `replay start --synthetic` (tras la selección) o
`--synthetic-only`.

| Caso | Resultado esperado | Observado |
|---|---|---|
| Primera versión | `new` | `new` |
| Repetición exacta | `duplicate` | `duplicate` |
| Revisión posterior | `revised` (el estado actual toma la nueva, el historial conserva ambas) | `revised`, 2 versiones |
| Versión antigua tardía | `stale` (el estado actual no retrocede) | `stale`, `updated_at` sin retroceder |
| Coordenadas imposibles | `quarantined` con `coordinates_out_of_range` | cuarentena sintética con el original |

### Resultados de la verificación

Medidos el 2026-11-16 en un equipo Windows 11 con Docker Desktop, con el catálogo 2025 de magnitud ≥ 4
ya descargado (detalle y salidas en [docs/evidence/005/](evidence/005/README.md)):

| Medida | Resultado |
|---|---|
| Selección de enero a abril de 2025, magnitud ≥ 4 | 5.301 eventos, registrados en `core.extraction` |
| Reproducción a 200 eventos/s | 5.301 eventos en 26,9 s (196,8 eventos/s, −1,6 % del objetivo) |
| Tiempo original | 5.301 de 5.301 coinciden con los ficheros descargados (0 diferencias) |
| Aislamiento | 10 tablas de `core` idénticas (recuento y suma) tras cada uno de los cinco escenarios |
| Pausa | efectiva 0,41 s después de volver la orden; el contador no avanza en pausa |
| Repetición tras `reset` | huella idéntica a la primera ejecución (`5301 · 270575545300917288502`) |
| Reinicio del consumidor a mitad (2.525 de 5.301) | huella idéntica; 5.301 mensajes `new`, ninguno duplicado, 0 en cuarentena |
| Pruebas automáticas | 682 pasan en el contenedor (`pytest tests`) |

**Supuestos y límites** (no medidos): la cadencia se mide hasta la confirmación de Kafka por mensaje y
no es un banco de pruebas de rendimiento (no cubre tres tamaños de entrada ni memoria); se ejecutó en un
solo equipo; el equipo Linux no se ha usado para esta verificación aunque el flujo es el mismo en
Docker; un grupo nuevo del consumidor empezaría desde el principio del topic de reproducción (retención
de 168 h) y repoblaría `replay` con reproducciones anteriores, sin afectar a `core`.

### Material heredado

`producer/app/replay.py` se sustituyó por el paquete `producer/app/replay/`.
`db/seeds/historical_2025.jsonl` (seis eventos ficticios) y `db/seeds/historical_1900.jsonl` (35
eventos reales descargados) se retiraron de Git: los casos de prueba los cubre el conjunto sintético y
los datos descargados no se versionan (se regeneran con `docker compose run --rm catalog-loader`).
Material de apoyo reutilizado frente a desarrollado: el catálogo, el consumidor y el modelo son de las
specs anteriores; la selección, la orden, el control, la comprobación de aislamiento y los casos
sintéticos son desarrollo de esta spec.

### Cómo ejecutar la demostración

Paso a paso en el [README](../README.md#demostración-de-la-defensa).

## Modelo conceptual

```mermaid
erDiagram
    COUNTRY ||--o{ EVENT_CURRENT : "contiene (opcional)"
    DATE ||--o{ EVENT_CURRENT : "ocurre en"
    EVENT_CURRENT ||--|{ EVENT_VERSION : "tiene versiones"
    EXTRACTION }o--o| RAW_PAYLOAD : "obtuvo"
    EXTRACTION ||--o{ EXCLUDED_EVENT : "descartó"
    PUBLISH_STATE ||--o| EVENT_CURRENT : "mismo identificador"
    QUARANTINE }o--o| EVENT_CURRENT : "puede referirse a"
    MESSAGE_LOG }o--o| EVENT_VERSION : "trajo"
```

- Un **terremoto** es la versión más reciente conocida de un evento de USGS y tiene **una o más
  versiones**, una por cada `updated` distinto.
- Un terremoto ocurre en **un día UTC** y, si su punto cae dentro de un polígono del catálogo,
  en **un país**.
- Una **extracción** es una consulta a USGS: puede haber guardado un **original** y haber
  descartado elementos que no son terremotos.
- El **estado de publicación** recuerda qué versión de cada evento envió el productor a Kafka.
- La **cuarentena** guarda los mensajes que no se pudieron tratar, con el original.
- El **registro de mensajes** anota cada mensaje procesado y su resultado.

## Modelo lógico

### Grano y claves

| Esquema | Tabla | Una fila representa | Clave |
|---|---|---|---|
| `core` | `dim_country` | Una entidad del catálogo Natural Earth | `country_id` |
| `core` | `dim_date` | Un día UTC | `date_id` |
| `core` | `extraction` | Una consulta a USGS | `extraction_id` |
| `core` | `raw_payload` | Un contenido original distinto | `content_sha256` |
| `core`, `replay` | `event_current` | La versión más reciente de un terremoto | `event_id` |
| `core`, `replay` | `event_version` | Una versión observada de un terremoto | `(event_id, updated_at)` |
| `core`, `replay` | `quarantine` | Un mensaje rechazado | `quarantine_id`; única `(kafka_topic, kafka_partition, kafka_offset)` |
| `core`, `replay` | `excluded_event` | Una versión de un elemento que no es un terremoto | `(event_id, updated_at)` |
| `core`, `replay` | `publish_state` | La última versión publicada de un evento | `event_id` |
| `core`, `replay` | `message_log` | Un mensaje procesado por el consumidor | `(kafka_topic, kafka_partition, kafka_offset)` |

`replay` usa las dimensiones de `core`. Durante la medición de índices existe además un esquema
`bench` con la misma plantilla, que se elimina al terminar.

### Relaciones

- `event_current.country_id` → `core.dim_country` (opcional: nulo = sin país).
- `event_current.event_date` → `core.dim_date` (obligatoria; columna generada desde `event_time`).
- `event_version.event_id` → `event_current.event_id` del mismo esquema, con borrado en cascada.
- `excluded_event.extraction_id` → `core.extraction` (opcional), también desde `replay`.
- Sin clave foránea, a propósito: `message_log` (un rechazo no corresponde a ninguna versión),
  `extraction.content_sha256` (la extracción sobrevive a la purga del original), `publish_state`
  y `quarantine` (un evento puede estar publicado y aún no consumido, o no existir nunca como
  válido).

### Regla de versiones

| Situación al llegar una versión | Estado actual | Historial | Resultado |
|---|---|---|---|
| Identificador desconocido | Se crea | Se añade | `new` |
| `updated_at` posterior al guardado | Se sustituye por completo | Se añade | `revised` |
| `updated_at` igual a uno ya visto | Sin cambios | Sin cambios | `duplicate` |
| `updated_at` anterior y nunca visto | Sin cambios | Se añade | `stale` |

La secuencia de la FAQ 12 (E1 a las 10:05 con 4,2; repetición; E1 a las 10:09 con 4,6; E1 a las
10:05 otra vez; E2 a las 10:12 con 3,1) da `new`, `duplicate`, `revised`, `duplicate`, `new`: 2
terremotos, 3 versiones y 5 mensajes registrados. Reprocesar 1.000 veces 50 mensajes deja los
mismos recuentos que la primera pasada ([db-tests.txt](evidence/002/db-tests.txt)).

## Modelo físico

El modelo se define en un único conjunto ordenado de ficheros SQL, aplicado por
[db/sql/apply.sh](../db/sql/apply.sh) al crear el volumen (y por las pruebas a una base
temporal):

| Fichero | Contenido |
|---|---|
| [010_roles_schemas.sql](../db/sql/010_roles_schemas.sql) | Esquemas `core` y `replay`; roles `observatory_writer` y `observatory_reader` |
| [020_dimensions.sql](../db/sql/020_dimensions.sql) | `dim_country`, cargada desde el GeoJSON con `pg_read_file`, y `dim_date` de 1900 a 2035 |
| [030_extraction.sql](../db/sql/030_extraction.sql) | `extraction`, `raw_payload` y `purge_raw_payload` |
| [040_event_tables.sql](../db/sql/040_event_tables.sql) | Plantilla por esquema: tablas de eventos y `apply_event_version` |
| [050_schema_rules.sql](../db/sql/050_schema_rules.sql) | Reglas de `replayed_at` en cada esquema y `replay.reset()` |
| [060_indexes.sql](../db/sql/060_indexes.sql) | Plantilla por esquema: índices secundarios que superaron la medición |
| [070_grants.sql](../db/sql/070_grants.sql) | Privilegios mínimos de los dos roles |

Restricciones principales: longitud en [−180, 180] y latitud en [−90, 90]; magnitud,
profundidad y coordenadas finitas (ni NaN ni infinito); `source`, `purpose`, `outcome` y
`encoding` dentro de sus valores; `replayed_at` nulo en `core` y obligatorio en `replay`;
cuarentena con al menos un motivo y con el original (JSON o texto); `raw_payload` con cuerpo o
ruta de fichero.

Tipos: `timestamptz` para todos los instantes (UTC); `double precision` para magnitud,
coordenadas y profundidad, que USGS publica como números de coma flotante; `text` con `CHECK`
para los valores cerrados, más fáciles de ampliar que un tipo enumerado; `jsonb` para los
originales; `text[]` para motivos y señales de calidad.

## Diccionario de datos

Convenciones: los instantes son `timestamptz` y se interpretan en UTC; «Ausencias» indica qué
se guarda cuando el dato no llega. Las tablas de eventos son idénticas en `core` y `replay`.

### `core.dim_country`

Origen: `frontend/public/datos/paises.geojson` (Natural Earth Admin 0), cargado una vez. 177 filas.

| Columna | Tipo | Significado y origen | Ausencias |
|---|---|---|---|
| `country_id` | `text`, clave | `ADM0_A3` de Natural Earth; no es necesariamente un código ISO | Nunca falta |
| `name_es` | `text` | `NAME_ES`, nombre mostrado en el panel | Nunca falta |
| `admin_name` | `text` | `ADMIN`, nombre administrativo en inglés | Nunca falta |
| `continent` | `text` | `CONTINENT` | Nunca falta |
| `subregion` | `text` | `SUBREGION` | Nunca falta |
| `iso_a3` | `text` | `ISO_A3`, informativo | `-99` en el catálogo se guarda como nulo (5 entidades: Noruega, Francia, Chipre del Norte, Somalilandia y Kosovo) |

### `core.dim_date`

Un día UTC por fila, de 1900-01-01 a 2035-12-31 sin huecos (49.673 filas), para poder contar
días sin eventos.

| Columna | Tipo | Significado | Ausencias |
|---|---|---|---|
| `date_id` | `date`, clave | Día UTC | — |
| `year`, `quarter`, `month`, `day` | `smallint` | Año, trimestre (1–4), mes (1–12) y día del mes | — |
| `iso_week` | `smallint` | Semana ISO 8601 (1–53) | — |
| `iso_dow` | `smallint` | Día de la semana ISO (1 = lunes, 7 = domingo) | — |
| `day_of_year` | `smallint` | Día del año (1–366) | — |

### `core.extraction`

Una fila por consulta a USGS (feed o catálogo), conservada indefinidamente.

| Columna | Tipo | Significado y unidad | Ausencias |
|---|---|---|---|
| `extraction_id` | `bigint` identidad, clave | Identificador interno | — |
| `source` | `text` | `usgs_feed` o `usgs_catalog` | — |
| `purpose` | `text` | `live`, `historical_load`, `gap_recovery` o `replay_selection` | — |
| `request_url` | `text` | URL completa consultada | — |
| `request_params` | `jsonb` | Parámetros enviados al catálogo: `endpoint` (`count`, recuento declarado, o `query`, descarga), `starttime`, `endtime`, `minmagnitude`, `eventtype` y `orderby` | Nulo en el feed |
| `window_start`, `window_end` | `timestamptz` | Intervalo pedido al catálogo; el final es posterior al inicio | Nulo en el feed |
| `requested_at` | `timestamptz` | Inicio de la consulta | — |
| `duration_ms` | `integer`, ms | Latencia total, reintentos incluidos | Nulo si no se midió |
| `attempt_count` | `smallint` | Intentos realizados (≥ 1) | 1 por defecto |
| `http_status` | `integer` | Último código HTTP | Nulo si no hubo respuesta (tiempo agotado) |
| `outcome` | `text` | `ok`, `not_modified`, `http_error`, `timeout`, `invalid_json` o `invalid_structure` | — |
| `error_detail` | `text` | Descripción del fallo (código HTTP, `Retry-After`, tiempo agotado, error de análisis). En una consulta correcta, describe los elementos no identificables (sin `id` o sin `updated` legible): cuántos y en qué posición de la respuesta | Nulo si fue correcta y todos los elementos eran identificables |
| `source_generated_at` | `timestamptz` | `metadata.generated` de la respuesta (ms Unix convertidos a UTC) | Nulo si no hubo cuerpo válido |
| `record_count` | `integer` | Elementos recibidos; en un recuento del catálogo (`endpoint = count`), los eventos que USGS declara para ese intervalo y filtro | Nulo si no hubo cuerpo válido |
| `earthquake_count`, `excluded_count`, `published_count` | `integer` | Reparto de los elementos: terremotos identificables; excluidos (otro tipo, sin tipo o no identificables), de modo que `record_count = earthquake_count + excluded_count`; versiones confirmadas por Kafka en esa consulta | Nulo si no hubo cuerpo válido; `published_count` nulo además si la publicación se interrumpió |
| `content_sha256` | `text` | Huella SHA-256: en el feed, de la lista de eventos en JSON canónico (no de la cabecera, que cambia en cada respuesta); en el catálogo, de los bytes del fichero descargado; en una respuesta ilegible, de los bytes recibidos. Un 304 repite la del último contenido | Nulo en fallos sin cuerpo y en recuentos |

### `core.raw_payload`

Una fila por contenido original distinto.

| Columna | Tipo | Significado y unidad | Ausencias |
|---|---|---|---|
| `content_sha256` | `text`, clave | Huella del contenido | — |
| `encoding` | `text` | `gzip` (cuerpo del feed en la base) o `file` (fichero en `data/`) | — |
| `body` | `bytea` | Cuerpo comprimido con gzip | Nulo para ficheros; se purga a los 7 días (`RAW_PAYLOAD_RETENTION_DAYS`) |
| `file_path` | `text` | Ruta bajo `data/` del fichero del catálogo: `usgs/catalog/<inicio>_<fin>_<filtro>_<huella12>.geojson`, inmutable | Nulo para cuerpos del feed |
| `byte_size` | `integer`, bytes | Tamaño sin comprimir | — |
| `first_seen_at`, `last_seen_at` | `timestamptz` | Primera y última vez que se obtuvo este contenido | — |

### `core.event_current`, `replay.event_current`

Una fila por terremoto: su versión más reciente.

| Columna | Tipo | Significado, unidad y conversión | Ausencias |
|---|---|---|---|
| `event_id` | `text`, clave | `id` de USGS | Sin él, el mensaje va a cuarentena |
| `source` | `text` | `usgs_feed` (feed en vivo) o `usgs_catalog` (catálogo histórico) | — |
| `event_time` | `timestamptz` | Ocurrencia: `properties.time`, ms Unix convertidos a UTC | Sin él, cuarentena |
| `event_date` | `date`, generada | Día UTC de `event_time`; clave foránea a `dim_date`; se recalcula si una revisión cambia `event_time` | — |
| `updated_at` | `timestamptz` | Versión en USGS: `properties.updated`, ms Unix convertidos a UTC | Sin él, cuarentena |
| `magnitude` | `double precision`, adimensional | `properties.mag`; su escala depende de `mag_type`; sin mínimo (hay magnitudes negativas) | Se guarda nulo; el panel muestra «ND» |
| `mag_type` | `text` | `properties.magType` (ml, mb, mw, md…) | Nulo |
| `longitude` | `double precision`, grados WGS84 | `geometry.coordinates[0]`, en [−180, 180] | Inválida: cuarentena |
| `latitude` | `double precision`, grados WGS84 | `geometry.coordinates[1]`, en [−90, 90] | Inválida: cuarentena |
| `depth_km` | `double precision`, km | `geometry.coordinates[2]`; negativa si el foco está sobre el nivel del mar | Se guarda nulo; el panel muestra «ND» |
| `place` | `text` | `properties.place`, descripción libre | Nulo |
| `country_id` | `text` | Entidad de `dim_country` que contiene el punto (punto en polígono en el consumidor) | Nulo = «Sin país asignado» (mar o fuera de todo polígono) |
| `quality_flags` | `text[]` | Anomalías señaladas sin rechazar el evento (p. ej. `negative_depth`) | Lista vacía |
| `first_ingested_at` | `timestamptz` | Primera vez que el consumidor guardó el evento; no cambia en las revisiones | — |
| `ingested_at` | `timestamptz` | Última escritura del consumidor (tiempo de procesamiento) | — |
| `replayed_at` | `timestamptz` | Instante de reproducción; el `event_time` original no se modifica | Siempre nulo en `core`; obligatorio en `replay` |

### `core.event_version`, `replay.event_version`

Una fila por versión observada.

| Columna | Tipo | Significado | Ausencias |
|---|---|---|---|
| `event_id` | `text` | Evento al que pertenece; clave foránea a `event_current` | — |
| `updated_at` | `timestamptz` | Identidad de la versión; clave junto con `event_id` | — |
| `source` | `text` | Procedencia de esta versión | — |
| `event_time` | `timestamptz` | Ocurrencia según esta versión | — |
| `magnitude`, `mag_type`, `depth_km` | como en `event_current` | Valores de esta versión, para ver los cambios sin abrir el original | Nulos como en `event_current` |
| `longitude`, `latitude` | `double precision`, grados | Posición según esta versión | — |
| `payload` | `jsonb` | `Feature` original de USGS, sin transformar | — |
| `received_at` | `timestamptz` | Momento en que el consumidor recibió la versión por primera vez | — |
| `kafka_topic`, `kafka_partition`, `kafka_offset` | `text`, `integer`, `bigint` | Mensaje que trajo la versión por primera vez; una repetición no lo cambia | — |

### `core.publish_state`, `replay.publish_state`

| Columna | Tipo | Significado | Ausencias |
|---|---|---|---|
| `event_id` | `text`, clave | Evento | — |
| `updated_at` | `timestamptz` | Última versión confirmada por Kafka; nunca retrocede | — |
| `published_at` | `timestamptz` | Momento de esa confirmación | — |

### `core.quarantine`, `replay.quarantine`

Una fila por mensaje rechazado; reprocesarlo no crea otra.

| Columna | Tipo | Significado | Ausencias |
|---|---|---|---|
| `quarantine_id` | `bigint` identidad, clave | Identificador interno | — |
| `kafka_topic`, `kafka_partition`, `kafka_offset` | `text`, `integer`, `bigint` | Posición del mensaje; única en conjunto | — |
| `event_id` | `text` | Identificador, si se pudo leer | Nulo |
| `reason_codes` | `text[]` | Todos los códigos de motivo encontrados (al menos uno) | — |
| `reason_detail` | `text` | Explicación legible, con la dimensión de calidad de cada motivo | — |
| `payload` | `jsonb` | Mensaje original, si es JSON | Nulo si no lo es |
| `raw_text` | `text` | Mensaje original como texto, si no es JSON | Nulo si es JSON; nunca faltan los dos |
| `is_synthetic` | `boolean` | Caso dañado a propósito para pruebas | `false` |
| `quarantined_at` | `timestamptz` | Momento del rechazo | — |
| `reprocessed_at` | `timestamptz` | Cuándo se reprocesó la fila con las reglas vigentes (spec 004); una fila reprocesada no se vuelve a tomar | Nulo = pendiente de reprocesar |
| `reprocess_result` | `text` | `recovered_new`, `recovered_revised`, `recovered_stale`, `recovered_duplicate` (resultado de la regla de versiones) o `still_rejected`; presente si y solo si `reprocessed_at` lo está | Nulo = pendiente |
| `reprocess_reason_codes` | `text[]` | Motivos vigentes si sigue rechazada tras el reprocesado | Nulo si se recuperó o está pendiente |

### `core.excluded_event`, `replay.excluded_event`

Versiones de elementos de USGS que no son terremotos (voladuras, explosiones…).

| Columna | Tipo | Significado | Ausencias |
|---|---|---|---|
| `event_id`, `updated_at` | `text`, `timestamptz` | Identidad de la versión excluida; clave | — |
| `event_type` | `text` | `properties.type` recibido (`quarry blast`, `explosion`…) | Nulo si no venía |
| `reason_code` | `text` | Motivo de la exclusión: `not_earthquake` (otro tipo) o `missing_type` (sin `properties.type`) | `not_earthquake` por defecto |
| `extraction_id` | `bigint` | Extracción en la que se vio por primera vez; clave foránea a `core.extraction` | Nulo |
| `payload` | `jsonb` | `Feature` original | — |
| `first_seen_at` | `timestamptz` | Primera observación | — |

### `core.message_log`, `replay.message_log`

Una fila por mensaje de Kafka procesado. Es una auditoría de la ingesta, no una fuente de
recuentos de terremotos.

| Columna | Tipo | Significado | Ausencias |
|---|---|---|---|
| `kafka_topic`, `kafka_partition`, `kafka_offset` | `text`, `integer`, `bigint` | Posición del mensaje; clave conjunta junto con `attempt` | — |
| `event_id` | `text` | Evento al que se refiere | Nulo si no se pudo leer |
| `updated_at` | `timestamptz` | Versión a la que se refiere | Nulo en los rechazos |
| `outcome` | `text` | `new`, `revised`, `stale`, `duplicate`, `excluded` (elemento que no es un terremoto) o `quarantined` | — |
| `attempt` | `smallint` | 0 = tratamiento original; 1 = reprocesado de la cuarentena. Forma parte de la clave primaria | 0 por defecto |
| `produced_at` | `timestamptz` | `ingested_at` del mensaje: cuándo lo obtuvo el productor | Nulo si el mensaje no lo trae |
| `processed_at` | `timestamptz` | Cuándo lo procesó el consumidor | — |

Denominadores que permite: mensajes recibidos (filas), versiones distintas (`event_version`),
terremotos actuales (`event_current`), repeticiones (`outcome = 'duplicate'`) y rechazos
(`outcome = 'quarantined'`). `processed_at − produced_at` mide el retraso del transporte.

## Índices

Solo las claves primarias y las restricciones únicas se crearon de antemano. Cada índice
secundario candidato (research.md R11) se midió con datos sintéticos de 10.000, 100.000 y
1.000.000 de eventos en un esquema `bench` con la misma plantilla, y se conserva si su consulta
es al menos 2 veces más rápida en mediana con 1.000.000 de filas (FR-027). Procedimiento
completo, equipo y todas las cifras: [index-benchmark.md](evidence/002/index-benchmark.md),
generado por [tests/benchmark/index_benchmark.py](../tests/benchmark/index_benchmark.py).
Equipo: Windows 11 con Docker Desktop (12 CPU y 7,6 GiB para el motor), PostgreSQL 16.4 con la
configuración por defecto (`shared_buffers` 128 MB), 2026-11-15.

### Índices conservados

Mediana de 5 ejecuciones con `EXPLAIN (ANALYZE, BUFFERS)`, en milisegundos, y búferes leídos
con 1.000.000 de filas:

| Índice | Consulta que resuelve | Sin índice | Con índice | Mejora | Tamaño |
|---|---|---:|---:|---:|---:|
| `event_current (event_time)` | Últimas 24 h del mapa | 53,6 ms · 20.073 búferes | 0,43 ms · 76 | ×126 | 21,5 MiB |
| ídem | Un mes agrupado por hora UTC | 51,3 ms · 20.071 | 21,8 ms · 228 | ×2,4 | ídem |
| `event_current (country_id, event_time)` | Un país en un mes | 55,1 ms · 20.073 | 0,28 ms · 324 | ×199 | 30,1 MiB |
| `event_current (magnitude, event_time)` | Magnitud ≥ 4 en un año | 40,4 ms · 20.073 | 1,00 ms · 988 | ×40 | 30,1 MiB |
| `core.extraction (requested_at)` parcial, solo feed correcto | `last_ingestion` | 79,0 ms · 19.608 | 0,016 ms · 4 | ×4.936 | 19,8 MiB |
| Clave primaria `event_version (event_id, updated_at)` | Versiones de un evento | 68,0 ms · 61.824 (copia sin clave) | 0,014 ms · 4 | ×4.859 | 70,6 MiB |

Los cuatro índices secundarios están en [060_indexes.sql](../db/sql/060_indexes.sql), cada uno
con un comentario que cita su consulta y su medición. Se crean en `core` y en `replay`; el de
`extraction`, solo en `core`, que es donde existe la tabla.

Matices de la medición:

- La mejora del índice de magnitud depende de la selectividad. Con la distribución de
  Gutenberg-Richter usada (b = 1 desde M1), M ≥ 4 es el 0,1 % de los eventos, como en el feed
  mundial completo. En el histórico de 2025, que solo contiene M ≥ 4, el filtro `min_mag=4` no
  selecciona nada y el planificador recorrerá la tabla o usará el índice de tiempo; el índice
  sigue sirviendo para umbrales más altos.
- La agrupación por hora de un mes es la consulta con menos margen (×2,4): un mes es el 8 % del
  año, y una vez localizadas las filas hay que agruparlas todas. El índice permite un recorrido
  solo de índice (228 búferes frente a 20.071).

### Índices descartados o solo medidos

| Candidato | Resultado con 1.000.000 de filas | Decisión |
|---|---|---|
| BRIN sobre `event_current (event_time)` | Últimas 24 h ×34 (1,56 ms) y un mes por hora ×2,0 (25,6 ms); ocupa 0,02 MiB | No se crea: R11 lo prevé solo como medición, y el B-tree es más rápido en las dos consultas (×126 y ×2,4). Es la alternativa si el espacio pasara a ser el límite |
| Índice aparte sobre `event_version (event_id)` | — | No se crea: la clave primaria ya empieza por `event_id`. El modelo anterior tenía este índice duplicado (`ix_event_versions_external_id`) |

### Razonamiento para 100 millones de registros

Las mediciones muestran la tendencia que importa. Sin índice, el tiempo crece en proporción a
las filas: unos 0,5 ms con 10.000, unos 5 ms con 100.000 y unos 50 ms con 1.000.000 en las
cuatro consultas sobre `event_current`, porque cada una lee toda la tabla (200, 2.000 y 20.000
búferes). Extrapolando, con 100 millones de filas serían unos 5 s por consulta y unos 2 millones
de búferes (16 GB) leídos, muy por encima de la memoria del equipo: la tabla dejaría de caber en
caché y el tiempo lo marcaría el disco.

Con índice, el coste depende de las filas que devuelve la consulta, no del tamaño de la tabla:
las últimas 24 h pasan de 0,013 a 0,06 y 0,43 ms al multiplicar la tabla por 10 y por 100,
porque esas 24 h contienen 10 y 100 veces más eventos en los datos sintéticos (uniformes en un
año). Con 100 millones de terremotos repartidos en muchos años, un día tendría un volumen real,
y la profundidad de un B-tree solo crece en uno o dos niveles. A esa escala harían falta además:

- **Particionar `event_current` y `event_version` por rango de `event_time`** (por año), para
  que las consultas por intervalo descarten particiones enteras y el mantenimiento (`VACUUM`,
  reindexado) trabaje por partes. La clave primaria tendría que incluir la clave de partición.
- **Revisar el BRIN**: con datos insertados en orden temporal, su tamaño (0,02 MiB frente a
  21 MiB con 1.000.000 de filas) lo convierte en la opción para las particiones antiguas, que
  apenas se escriben.
- **Agregados precalculados por día y país**, alimentados desde `event_current`, para los
  gráficos que recorren todo el histórico. Mantienen el principio VII si se recalculan desde el
  estado actual y no se incrementan con contadores.
- **Más memoria para PostgreSQL** (`shared_buffers`, `work_mem`) que los valores por defecto
  usados aquí.

Nada de esto hace falta para el volumen del proyecto (unos 16.000 eventos del histórico obligatorio
más el feed), donde las cuatro consultas tardan menos de un milisegundo con índice.
