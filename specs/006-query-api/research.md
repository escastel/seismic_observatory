# Investigación y decisiones: API de consulta (spec 006)

Cada decisión indica qué se elige, por qué y qué se descartó.

## R1. Modo real o reproducción: un pool por modo

- **Decisión**: la API abre dos pools de solo lectura, uno con `search_path = core` y otro con
  `search_path = replay, core`. El parámetro `mode` elige el pool de la petición; las consultas
  siguen sin cualificar (`event_current`), como en el consumidor. `dim_country` se resuelve en
  `core` en ambos casos.
- **Por qué**: una petición solo usa un pool, así que no puede mezclar esquemas; el texto de la
  consulta es idéntico en ambos modos y no hay `UNION` ni parámetro de esquema que interpolar. El
  rol lector ya tiene `SELECT` en ambos esquemas (`070_grants.sql`).
- **Descartado**: interpolar el nombre de esquema en el SQL (riesgo de inyección y de olvidar un
  filtro); una vista que una ambos esquemas (mezcla por diseño); rutas distintas
  (`/api/replay/...`, contradice la decisión «`mode` como parámetro»).
- **Detalle**: el pool de reproducción se abre en segundo plano con reintento, igual que el real.
  Si el pool pedido no existe, 503 JSON; que falle el de reproducción no afecta al real.

## R2. Qué es «real» y qué es «sintético»

- **Decisión**: en modo real la condición `NOT starts_with(event_id, 'synthetic-') AND NOT
  ('synthetic' = ANY(quality_flags))` se aplica siempre, como defensa en profundidad (`core` no
  debería contener sintéticos, pero la API no depende de ello). En modo `replay` se devuelven los
  sintéticos con `properties.synthetic = true` y el parámetro `exclude_synthetic=true` los quita.
- **Por qué**: el consumidor marca los sintéticos con el prefijo `synthetic-` en el identificador
  y con `synthetic` en `quality_flags` (spec 004). Usar ambas señales evita perder uno marcado
  solo por una.
- **Efecto en el plan de ejecución**: es un filtro residual sobre filas ya acotadas por
  `event_time`; no necesita índice (R9).

## R3. `last_ingestion` y `salud`

- **Decisión**: `last_ingestion = max(requested_at)` de `core.extraction` con
  `source = 'usgs_feed' AND outcome IN ('ok','not_modified')`, que coincide con el predicado del
  índice parcial `extraction_last_ok_feed_idx` (`060_indexes.sql`). Se emite en milisegundos Unix;
  `null` si no hay ninguna.
- **Desviación consciente del encargo** («consulta `ok`»): `not_modified` significa que USGS
  respondió y no había nada nuevo, es decir, la ingesta sigue sana. Si no contara, un tramo
  tranquilo sin cambios haría parecer parada una ingesta correcta (el contrato dice «última
  consulta correcta a USGS»). Se documenta en la memoria; cambiar a solo `ok` es un cambio de una
  línea si se prefiere.
- **Salud**: responde siempre 200 (el healthcheck de Docker usa esta ruta y la API sigue viva
  aunque la base no lo esté); `status` es `ok` o `degraded`, con `database` (`ok`/`unavailable`)
  y `replay_database`, `last_ingestion`, `generated`. Sin credenciales, sin host, sin versión.
  Con la base caída `last_ingestion` es `null` y `status` es `degraded` (nunca se rellena con un
  valor antiguo en silencio).
- **Descartado**: el último `ingested_at` de `event_current` (lo que hacía la API heredada: un
  reproceso o una carga histórica lo mueven sin que USGS haya sido consultado).

## R4. Errores

- **Decisión**: manejadores globales. Fallos de la base (`OSError`, `asyncpg.PostgresError`,
  `asyncpg.InterfaceError`, `TimeoutError`) y pool inexistente → 503 con cuerpo
  `{"error": "database_unavailable", "detail": "..."}`. Validación → 422 con
  `{"error": "invalid_parameters", "detail": [{"param": "...", "message": "..."}]}`. Todo error
  inesperado → 500 con cuerpo JSON genérico y registro en log; nunca una lista vacía.
- **Tiempo máximo de consulta**: `command_timeout` de 10 s en el pool; vence → 503.
- **Cambio sobre lo heredado**: la API devolvía 400 para rangos inválidos; pasa a 422.
- **Validaciones**: `start` y `end` ISO 8601 con zona (sin zona se rechaza: no se adivina);
  `start < end` (iguales también se rechazan); `min_mag` numérico finito; `country_id` de 1 a 8
  caracteres alfanuméricos; `limit` entre 1 y el máximo; `offset ≥ 0`; `mode` en `live|replay`.
  Los parámetros desconocidos se ignoran (FastAPI), para no romper al frontend entregado (R8).

## R5. Forma de la respuesta de eventos y paginación

- **Decisión**: ver [contracts/api.md](contracts/api.md). Resumen: `metadata` con `generated`,
  `last_ingestion`, `mode`, `count`, `total`, `truncated`, `limit`, `offset`, `next_offset`,
  `null_magnitude` y `quarantined`; en `replay` además `label = "REPRODUCCIÓN"` y
  `last_replayed_at`.
- **Máximo de puntos**: 1.000 (configurable con `API_MAX_FEATURES`). Coincide con el `limit` que
  ya envía el frontend entregado. `limit` por defecto = máximo.
- **Paginación**: `limit` + `offset` con orden total `event_time DESC, event_id ASC` (estable aun
  con empates de tiempo). `next_offset` es `null` en la última página. Limitación documentada:
  con datos en vivo, una llegada entre dos páginas desplaza el desplazamiento; el cliente que
  recorre páginas debe fijar `end` (como en cualquier paginación por `offset`). No se usa cursor
  por clave: complica el contrato y el volumen no lo exige.
- **Página y total en una sola instantánea**: `REPEATABLE READ` de solo lectura para que
  `count`, `total` y `null_magnitude` sean coherentes entre sí.
- **Tiempos**: milisegundos como entero calculado con `(dt - epoch) // 1 ms` (exacto y válido
  antes de 1970 en Windows y Linux; la spec 004 ya tiene casos anteriores a 1970).
- **Finitud**: la base ya impide NaN e infinito en magnitud y profundidad
  (`event_current_magnitude_finite`); el serializador los convierte además en `null` y la
  respuesta se genera con `allow_nan=False` como red de seguridad.
- **Magnitud nula** (`null_magnitude`): `{count, excluded}`; `count` son los eventos con
  magnitud nula que cumplen todos los filtros salvo `min_mag`, y `excluded` es `true` cuando
  `min_mag` está presente (es decir, no están en `features`).
- **Geometría inválida**: `event_current` impone `NOT NULL` y los rangos de longitud y latitud,
  de modo que un evento sin punto válido **no puede estar** en el estado actual: la spec 004 lo
  manda a cuarentena. Por eso `features` nunca tiene un elemento sin punto y la evidencia consiste
  en inyectar un mensaje con coordenadas inválidas y comprobar que no aparece como elemento y que
  `metadata.quarantined.invalid_geometry` lo cuenta. `quarantined` cuenta, en el esquema del
  modo, las filas de `quarantine` no sintéticas, con el subconjunto de motivos de geometría
  (`geometry_missing`, `geometry_not_point`, `coordinates_*`); es un contador global del esquema,
  no filtrado por la consulta (la cuarentena no guarda tiempo de ocurrencia fiable).

## R6. Estadísticas

- **Forma**: ver `contracts/api.md`. `GET /api/estadisticas` acepta los mismos parámetros de
  filtro que el mapa (`start`, `end`, `min_mag`, `country_id`, `mode`, `exclude_synthetic`) y no
  acepta paginación.
- **Mismo filtro**: `filters.py` ofrece una única función `build_where(filters)` usada por
  eventos y estadísticas. Una prueba compara, para una batería de filtros, `metadata.total` del
  mapa con `total` de las estadísticas.
- **Periodo por defecto**: igual que el mapa (últimas 24 horas) en modo real; en `replay`, todo
  el espacio de reproducción. El periodo efectivo se devuelve siempre (`period.start/end`,
  `period.default_applied`).
- **Ventanas por hora**: `date_bin('1 hour', event_time, TIMESTAMPTZ '2000-01-01 00:00:00+00')`
  alinea a la hora UTC con independencia de la zona de sesión; `generate_series` rellena las
  horas vacías con 0 entre el inicio y el fin efectivos; el fin es exclusivo. Si el periodo
  produjera más de 10.000 ventanas (≈ 416 días), 422 con mensaje que pide acotar (no se trunca).
- **Por qué ventanas fijas** (justificación para la memoria): son reproducibles (la misma consulta
  da lo mismo), no dependen del instante de la petición, coinciden con el principio VII y se
  resuelven con el índice por `event_time`; una ventana deslizante cambiaría con cada petición y
  no sería comparable entre mapa, tabla y panel.
- **País**: agrupación por `country_id` con `LEFT JOIN dim_country`; el país nulo sale con
  `country_id: null` y `country_name: "Sin país asignado"`.
- **Distribuciones**: magnitud por tramos de 1 (`floor(magnitude)`, incluidos los negativos) y
  profundidad por tramos `<0`, `0–70`, `70–300`, `≥300` km; `unvalued` cuenta aparte las nulas
  (no son ceros ni se descartan en silencio).
- **Comparación histórica**: bloque `comparison` con un periodo reciente de 24 horas y una
  referencia (por defecto el año UTC 2025, configurable con el parámetro `baseline_year`). Aplica
  `country_id`, `min_mag` y `exclude_synthetic` a ambos (los mismos filtros de magnitud y ámbito,
  principio VII); `start` y `end` definen el periodo principal y no la comparación. Media diaria
  = eventos de la referencia / días del año (365 o 366, **incluye los días sin eventos**); si la
  media es 0, `ratio` es `"ND"`. Siempre incluye `warning` (periodo reciente posiblemente
  incompleto: USGS revisa y añade eventos durante horas). En modo `replay` el instante de anclaje
  es `end` o, si falta, el último `event_time` del espacio de reproducción, la referencia se
  calcula sobre lo reproducido y se avisa de ello.
- **Truncado**: las agregaciones se calculan en SQL sobre **todo** el conjunto que cumple el filtro
  y nunca sobre la página enviada, así que no hay «estadística global sobre la muestra». La
  respuesta incluye `scope: "complete"`, `total` y, cuando el mapa con ese filtro se truncaría,
  `map_truncated: true` para que el panel lo muestre. **Desviación** respecto de la alternativa
  «rechazar»: rechazar obligaría a quitar las estadísticas justo cuando hay más datos.
- **Instantánea**: todas las agregaciones de una respuesta se ejecutan en una transacción
  `REPEATABLE READ` de solo lectura (cifras coherentes entre sí aunque llegue un mensaje).
- **Sin contadores incrementales**: no hay tablas nuevas; una revisión cambia el estado actual y
  la siguiente petición lo refleja; una versión antigua tardía no cambia el estado actual.

## R7. Acceso

- **CORS**: se mantiene `CORSMiddleware` con `CORS_ORIGINS` (la lista ya la valida
  `common/settings.py`: orígenes exactos, sin comodín), `allow_methods=["GET","OPTIONS"]`,
  `allow_headers=["Content-Type","ngrok-skip-browser-warning"]` y se cambia
  `allow_credentials` de `True` a `False` (sin cookies). Se valida `max_age` de 600 s.
- **Rutas**: solo `/api/eventos`, `/api/estadisticas`, `/api/salud` y `/api/openapi.json`. Se
  desactivan `/docs` y `/redoc` (cargan recursos de CDN y no son contrato). Ninguna ruta escribe.
- **Puerto y proceso**: ya cumple (`127.0.0.1:8000:8000` en Compose; uvicorn en `0.0.0.0:8000`
  en el contenedor). Una prueba comprueba el conjunto de rutas y que ninguna acepta métodos de
  escritura. La API no importa ningún cliente de USGS.

## R8. Alias y rutas heredados

Comprobación del frontend entregado (`frontend/src/app/app.component.ts`, copia del de
`resources/observatorio-sismico/frontend`):

| Heredado | ¿Lo usa el frontend entregado? | Decisión |
|---|---|---|
| `format=geojson` | Sí, lo envía | Se acepta y se ignora (la respuesta ya es siempre `FeatureCollection`); no se documenta. |
| `limit` | Sí (1000) | Se conserva: es el tamaño de página del contrato. |
| `country` (nombre) | Sí | Se retira (el contrato filtra por `country_id`). El parámetro se ignora, de modo que el filtro por país del frontend entregado deja de aplicarse hasta que la spec 007 lo migre a `country_id`. **Traspaso a 007.** |
| `date_from`, `date_to`, `min_magnitude`, `max_magnitude` | No | Se retiran. |
| `format=json` y la respuesta `{items,count,limit,offset}` | No | Se retira. |
| `/api/estadisticas/paises`, `/api/estadisticas/timeline` | No (solo `/api/estadisticas`) | Se retiran; los datos están en `/api/estadisticas`. |
| `/api/health` | No (Compose usa `/api/salud`) | Se retira. |
| Propiedad `country` (duplicado de `country_name`) | Sí, en el popup | Se retira; el contrato define `country_name`. `continent` y `subregion` se conservan (los usa el popup y salen de `dim_country`). **Traspaso a 007.** |

No queda ningún alias conservado, por lo que no hace falta fecha de retirada.

## R9. Modelo e índices: sin cambios

- Las consultas se apoyan en los índices de la spec 002: `event_current_event_time_idx` (periodo
  y orden), `event_current_country_event_time_idx` (país + periodo),
  `event_current_magnitude_event_time_idx` (magnitud + periodo) y `extraction_last_ok_feed_idx`
  (última ingesta). Se comprueba con `EXPLAIN (ANALYZE, BUFFERS)` para: periodo por defecto,
  periodo con `min_mag`, país + periodo, estadísticas por hora y `last_ingestion`; el resultado va
  a `docs/evidence/006/`.
- Riesgo asumido: `ORDER BY event_time DESC, event_id` sobre `LIMIT` usa el índice de
  `event_time` con ordenación incremental; si la medición mostrara un escaneo secuencial a
  17.000–1.000.000 de filas, se documenta y solo entonces se propone un índice (cambio de modelo
  con necesidad demostrada).
- El contador de cuarentena y la comparación anual agregan sobre tablas pequeñas o por rango
  de `event_time`; se miden con el resto.

## R10. Medición de rendimiento (§10)

- **Procedimiento**: `tests/benchmark/api_latency.py` lanza N = 30 peticiones secuenciales tras
  5 de calentamiento a tres tamaños de resultado (página pequeña ~10 eventos, página de 1.000 y
  estadísticas de un año de datos de 2025), informa mediana, p95 y máximo, e indica equipo
  (CPU, RAM, SO, versión de Docker) y volumen de datos. También mide con la base de la spec 002
  poblada a 1.000.000 de filas en el esquema de `bench` si está disponible.
- **Datos**: si el esquema `core` local no tiene el año 2025, la medición usa el espacio de
  reproducción cargado con la selección de la spec 005 (mismas tablas e índices) y lo indica.
- **Criterio**: SC-008 (< 2 s).

## R11. Pruebas de comportamiento con el sistema real

- Los casos de la historia 8 se ejecutan contra la API real (contenedor `api`) alimentada por el
  consumidor real o, para los casos de revisión y versión antigua tardía, con las funciones del
  modelo (`apply_event_version`) y los mensajes sintéticos de la spec 004, siempre en
  `observatory_test` para pruebas y en el sistema levantado para la evidencia de `verify-stack`.
- Los sintéticos se inyectan en `replay` (nunca en `core`), salvo la prueba negativa de modo real,
  que inserta un sintético en `core` en la base de pruebas para demostrar que no aparece.
- Base caída: se detiene el contenedor `postgres` y se comprueban 503 JSON en eventos y
  estadísticas y `degraded` en salud; se vuelve a levantar y se comprueba la recuperación del
  pool sin reiniciar la API.
