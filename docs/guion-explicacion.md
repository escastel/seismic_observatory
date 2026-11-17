# Guion de apoyo: flujo completo del observatorio

Documento de apoyo para explicar oralmente el sistema. No es un texto para leer en voz alta: cada etapa
resume qué hace, dónde está en el repositorio, por qué se diseñó así y dónde está la evidencia. Las
cifras y decisiones proceden de [report.md](report.md), [README.md](../README.md) y la
[constitución](../.specify/memory/constitution.md); si algo no aparece ahí, no se afirma.

Flujo: **USGS → productor → Kafka → consumidor → PostgreSQL → API → panel Angular (Netlify, vía ngrok)**.

---

## 1. Fuente y productor (USGS → productor)

- **Qué hace**: cada 60 s consulta el feed `all_day.geojson` (últimas 24 h) y registra cada consulta en
  `core.extraction`, tanto si da datos como si falla. Para el histórico, el `catalog-loader` pide a la API
  FDSN de USGS los recuentos por mes y descarga cada intervalo; si supera 20.000 eventos lo divide.
- **Dónde está**: [producer/app/](../producer/app/) (`usgs.py`, `catalog_load.py`, `fingerprint.py`,
  `persistence.py`, `publisher.py`, `gaps.py`).
- **Decisión principal**: solo se publican las versiones con `updated` posterior a la ya publicada, y se
  marcan como publicadas **después** de que Kafka confirme el mensaje. *Justificación*: la constitución
  (principio II) exige esperar la confirmación de Kafka antes de marcar una versión como publicada; así un
  fallo entre medias provoca una repetición, nunca una pérdida. La huella de cada respuesta se calcula sobre
  la lista de eventos y no sobre la respuesta completa, porque `metadata.generated` cambia en cada
  regeneración aunque los eventos sean los mismos.
- **Evidencia**: [feed](evidence/003/feed.md), [source-failures](evidence/003/source-failures.md),
  [catalog-load](evidence/003/catalog-load.md), [retention](evidence/003/retention.md),
  [gap-recovery](evidence/003/gap-recovery.md).
- **Preguntas previsibles**
  - *¿Por qué no guardar cada respuesta completa?* Porque respuestas con los mismos eventos ocupan una sola
    fila (huella sobre los eventos) y los originales se purgan a los 7 días sin observarse; el report estima
    menos de 175 MB en ese plazo.
  - *¿Qué pasa si USGS no responde?* Hasta 4 intentos con esperas de 1, 2 y 4 s (o `Retry-After`); la consulta
    queda registrada con su resultado, nada se borra y el ciclo siguiente lo reintenta. Si la parada supera
    las 24 h, el productor avisa del hueco y la orden de recuperación se lanza con el `catalog-loader`.

## 2. Kafka (broker)

- **Qué hace**: transporta los mensajes del feed, del catálogo y de la reproducción en tres topics:
  `earthquakes.live`, `earthquakes.catalog` y `earthquakes.replay`. La clave de cada mensaje es el
  identificador del evento.
- **Dónde está**: servicio `kafka` de [compose.yaml](../compose.yaml) (Kafka 3.7 en modo KRaft, imagen
  Confluent 7.7.1); la creación de topics está en `common/`.
- **Decisión principal**: el productor publica los originales **antes** de que nadie los procese, y el
  consumidor relee desde su último offset confirmado. *Justificación*: la semántica es «al menos una vez»
  (constitución, principio II; resumen del README, sección 1), y con clave por evento los mensajes de un
  mismo evento llegan en orden a la misma partición.
- **Evidencia**: [consumer-restart de la 005](evidence/005/v7-consumer-restart.md) (reinicio a mitad sin
  cambio de resultado) y [startup](evidence/002/startup.md).
- **Preguntas previsibles**
  - *¿Por qué tres topics y no uno?* El topic de reproducción no puede mezclarse con los datos reales
    (principio VI), y el catálogo histórico se distingue del feed por su procedencia.
  - *¿Cuánto se conservan los mensajes?* El README indica 7 días para los topics de datos y 168 h para el de
    reproducción; el consumidor puede releer ese plazo.

## 3. Consumidor (validación, cuarentena, cruce espacial, persistencia)

- **Qué hace**: por cada mensaje abre una transacción, aplica las reglas, cruza el punto con el polígono del
  país, aplica la versión en PostgreSQL y anota el mensaje en `message_log`. Confirma la transacción y solo
  después confirma el offset de Kafka. Lo que no puede tratarse va a cuarentena con su original y su motivo.
- **Dónde está**: [consumer/app/](../consumer/app/) (`main.py`, `rules.py`, `spatial.py`, `persistence.py`,
  `reprocess.py`).
- **Decisión principal**: solo va a cuarentena lo que **no puede tratarse**; el resto se conserva, y las
  anomalías se marcan. Magnitud o profundidad ausentes se guardan como nulas, nunca como cero. *Justificación*:
  el principio III obliga a conservar o señalar; una profundidad negativa es un foco sobre el nivel del mar
  (mínimo observado −2,74 km), y sustituir un nulo por cero falsearía medias y mínimos.
- **Evidencia**: [acceptance](evidence/004/acceptance.md), [restart](evidence/004/restart.md),
  [spatial-and-counts](evidence/004/spatial-and-counts.md), [quality-queries](evidence/004/quality-queries.md),
  [reprocess](evidence/004/reprocess.md).
- **Preguntas previsibles**
  - *¿Por qué un evento sin país no se asigna al más cercano?* La constitución (principio IV) lo prohíbe: queda
    con país nulo y el panel muestra «Sin país asignado». El país sale de punto en polígono sobre Natural
    Earth, nunca del texto de `place`.
  - *¿Qué pasa si el consumidor se cae a mitad?* El offset no avanza por encima del mensaje fallido y, al
    volver, reprocesa el mismo mensaje sin duplicar: la prueba de reinicio de la 004 y la 005 lo demuestran.

## 4. PostgreSQL (modelo de datos)

- **Qué hace**: guarda el estado actual (`event_current`), el historial de versiones (`event_version`),
  la cuarentena, la procedencia y el registro de mensajes, en dos esquemas con la misma plantilla: `core`
  (real) y `replay` (reproducción). La función `apply_event_version` decide `new`, `revised`, `stale` o
  `duplicate`.
- **Dónde está**: [db/sql/](../db/sql/) (roles y esquemas, dimensiones, extracción, eventos, calidad,
  reglas, índices y privilegios).
- **Decisión principal**: la regla de versiones vive en la función de la base, junto a sus restricciones, y
  hay tres roles (propietario, escritor y lector). *Justificación*: la regla se prueba con SQL y devuelve el
  resultado que se cuenta; la API, única pieza expuesta a Internet, usa un rol que no puede modificar datos
  aunque falle. Los índices secundarios solo se conservan si su consulta es al menos 2 veces más rápida.
- **Evidencia**: [model-structure](evidence/002/model-structure.md), [index-benchmark](evidence/002/index-benchmark.md),
  [db-tests](evidence/002/db-tests.txt), [v3-isolation](evidence/005/v3-isolation.md) (aislamiento de `core`
  frente a la reproducción).
- **Preguntas previsibles**
  - *¿Por qué dos esquemas y no una columna «origen»?* El aislamiento queda garantizado por la estructura:
    una consulta o un borrado de `replay` no puede tocar `core`.
  - *¿Por qué no hay una fila «Sin país asignado» en la dimensión?* No se inventa una entidad; el texto lo pone
    la presentación.

## 5. API de consulta (FastAPI)

- **Qué hace**: responde `GET /api/eventos`, `/api/estadisticas` y `/api/salud` con un `FeatureCollection`,
  filtros (`start`, `end`, `min_mag`, `country_id`, `mode`), paginación y estadísticas calculadas sobre el
  total del filtro. Solo lee, nunca consulta USGS.
- **Dónde está**: [api/app/](../api/app/) (`main.py`, `queries.py`, `filters.py`, `stats.py`, `serialize.py`,
  `db.py`). El contrato es la fuente de verdad (principio VIII).
- **Decisión principal**: el modo elige **la conexión** (`core` para `live`; `replay, core` para `replay`),
  así una petición nunca mezcla datos reales y de reproducción; y ante un fallo de base responde 503, nunca
  «cero eventos». *Justificación*: principios VI y VIII. El `last_ingestion` sale de las consultas registradas
  a USGS y no de la última fila escrita, porque una recarga movería esa fecha sin que USGS haya sido consultado.
- **Evidencia**: [v1-contract](evidence/006/v1-contract.md), [v12-database-down](evidence/006/v12-database-down.md),
  [v15-plans](evidence/006/v15-plans.md), [v16-latency](evidence/006/v16-latency.md), y el
  [índice de la 006](evidence/006/README.md).
- **Preguntas previsibles**
  - *¿Por qué la API no puede escribir?* Es la única pieza expuesta a Internet a través del túnel; por eso se
    conecta con el rol de solo lectura (`observatory_reader`).
  - *¿Por qué 503 y no una lista vacía si la base cae?* Una lista vacía sería una respuesta válida falsa; el
    contrato exige un error explícito.

## 6. Panel Angular, Netlify y ngrok

- **Qué hace**: muestra mapa, tabla, análisis y estado de frescura, leyendo solo la API. Netlify publica la
  SPA; el backend sigue en este equipo y se expone con un túnel ngrok.
- **Dónde está**: [frontend/src/app/](../frontend/src/app/) (`lib/` con la lógica pura, `map/`, `table/`,
  `charts/`, `status/`, `filters/`, `data/`); configuración del despliegue en
  [netlify.toml](../netlify.toml) y en [frontend/public/config.json](../frontend/public/config.json); el túnel
  es el servicio opcional `tunnel` de Compose, fuera del proceso de la API.
- **Decisión principal**: el backend no se lleva a la nube; Netlify solo publica la SPA y el túnel se
  configura aparte. *Justificación*: las instrucciones del proyecto (CLAUDE.md) fijan ese alcance, y la
  constitución (principio VIII) obliga a que el panel distinga última lectura, generación y última ingesta, y
  a avisar cuando el backend no responde conservando la última lectura. Los gráficos son HTML y SVG propios,
  sin biblioteca, y la lógica pura se prueba con Vitest.
- **Evidencia**: [README de la 007](evidence/007/README.md) (incluida la sección «Prueba desde Netlify»),
  [V1-panel.png](evidence/007/V1-panel.png), [N1-netlify-load.png](evidence/007/N1-netlify-load.png),
  [N3-netlify-tunnel-closed.png](evidence/007/N3-netlify-tunnel-closed.png).
- **Preguntas previsibles**
  - *¿Qué pasa si se cierra el túnel con el panel abierto?* Aparece el aviso de backend inaccesible con la
    última lectura y su hora; al reabrirlo vuelve a «Datos al día» sin recargar (N3 en la 007).
  - *¿Qué no está probado todavía?* Desde otro dispositivo físico y en Linux; conviene decirlo tal cual.

---

## Orden de una demostración

Según [README.md §4, §5 y §10](../README.md). Todas las órdenes se lanzan desde la raíz del repositorio.

1. Tener `.env` con las contraseñas locales y `NGROK_AUTHTOKEN` y `NGROK_DOMAIN` (no mostrar su contenido en pantalla).
2. Levantar el stack y comprobar la salud:
   ```bash
   docker compose up --build -d
   docker compose ps
   curl -s http://127.0.0.1:8000/api/salud
   ```
3. Si el histórico no está cargado, `docker compose run --rm catalog-loader` (README §7).
4. Levantar el túnel y comprobarlo desde fuera:
   ```bash
   docker compose --profile tunnel up -d
   docker compose --profile tunnel logs tunnel
   curl -s "https://TU-DOMINIO.ngrok-free.app/api/salud" -H "ngrok-skip-browser-warning: 1"
   ```
5. Abrir el panel publicado en Netlify. Si la URL del túnel ha cambiado, antes hay que actualizar `apiUrl` en
   `frontend/public/config.json`, recompilar y publicar (README §10, pasos 3 y 8).
6. Opcional: la reproducción acelerada (README, «Demostración de la defensa») para mostrar actividad sin
   terremotos reales; se etiqueta «REPRODUCCIÓN» en el panel.
7. Al terminar, parar el túnel con `docker compose --profile tunnel stop tunnel`.

---

## Tu decisión técnica propia

Elige tú una decisión del proyecto, escribe aquí cuál es y por qué; esta sección la redacta y defiende la usuaria.

Candidatas (títulos de la tabla «Decisiones propias del modelo» de [report.md](report.md)):

- Esquemas `core` (real) y `replay` (reproducción) con la misma plantilla de tablas
- Regla de versiones en la función `apply_event_version`
- País nulo cuando el punto no cae en ningún polígono
- Magnitud y profundidad anulables, sin mínimo
- Tres roles de base de datos (propietario, escritor, lector)
- Registro de cada mensaje procesado (`message_log`)
- Originales del feed comprimidos, una vez por huella y durante 7 días
- Índices secundarios solo si su consulta es al menos 2 veces más rápida
