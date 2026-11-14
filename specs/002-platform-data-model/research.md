# Research: Plataforma y modelo de datos

**Fecha**: 2026-11-14 · **Spec**: [spec.md](spec.md)

No quedaban marcadores NEEDS CLARIFICATION. Este documento fija las decisiones técnicas. Las
marcadas como **verificado** se comprobaron el 2026-11-14 en un contenedor desechable
`postgres:16.4` con el catálogo real montado, sin tocar la base de desarrollo.

## R1. Organización en esquemas

- **Decisión**: tres esquemas. `core` contiene los datos reales (feed y catálogo histórico), las
  dimensiones compartidas y el registro de extracciones. `replay` contiene una réplica
  estructural de las tablas de eventos. `bench` se crea y se elimina durante las mediciones.
- **Razón**: el aislamiento exigido (FR-023) queda garantizado por la estructura, no por una
  columna que cualquier consulta puede olvidar filtrar. El mismo `event_id` puede existir en
  ambos esquemas sin interferir (**verificado**).
- **Alternativas**: columna `mode` en tablas compartidas (es el diseño actual y permite que un
  evento de reproducción sobrescriba uno real); base de datos separada (obliga a duplicar
  dimensiones y conexiones sin beneficio).

## R2. Una sola definición para `core` y `replay`

- **Decisión**: las tablas de eventos se definen una vez en un fichero SQL parametrizado con la
  variable `schema` de `psql`, que el script de inicialización ejecuta para `core` y para
  `replay`. Los servicios trabajan con nombres sin calificar y fijan `search_path` al conectar
  (`core` o `replay, core`).
- **Razón**: «reutilizar sin bifurcar» (principio VI) también en el SQL; el consumidor usa las
  mismas sentencias para ambos destinos. **Verificado**: la plantilla se aplica dos veces sin
  cambios.
- **Alternativas**: duplicar el DDL a mano (deriva inevitable); herencia o particionado de
  PostgreSQL (complejidad sin relación con el requisito).

## R3. Escritura atómica como función de base de datos

- **Decisión**: función `apply_event_version(...)` en cada esquema. Primero hace el upsert
  condicionado del estado actual (`WHERE EXCLUDED.updated_at > actual.updated_at`), después
  inserta la versión con `ON CONFLICT DO NOTHING`, y devuelve `new`, `revised`, `stale` o
  `duplicate`.
- **Razón**: la regla de versiones vive junto a las restricciones que la protegen, se prueba con
  SQL puro (historia 2 de la spec) y el valor devuelto permite contar cuántos mensajes fueron
  novedad, revisión, repetición o versión atrasada, que es evidencia directa para el apartado de
  calidad. **Verificado** con la secuencia de la FAQ 12: 2 eventos actuales y 3 versiones, E1
  con magnitud 4,6; una versión antigua nunca vista devuelve `stale` y se conserva en el
  historial sin tocar el estado actual.
- **Alternativas**: dos sentencias desde Python dentro de una transacción (misma garantía, pero
  la lógica queda repartida y no se puede probar sin el consumidor); `MERGE` (no ofrece nada que
  `ON CONFLICT` no dé aquí y es menos claro con la condición de versión).

## R4. Fecha del evento como columna generada

- **Decisión**: `event_date` es una columna generada a partir de `event_time` en UTC, con clave
  foránea a `dim_date`.
- **Razón**: si una revisión cambia el tiempo de ocurrencia, la fecha se corrige sola; no puede
  quedar desincronizada. **Verificado**: `2026-10-28 00:30+02` produce `2026-10-27`.
- **Alternativas**: columna normal mantenida por el consumidor (un punto más donde equivocarse);
  prescindir de la dimensión (se pierde el denominador con días sin eventos, que el enunciado
  exige en la comparación histórica).

## R5. Dimensión de país cargada por la propia base

- **Decisión**: el script de inicialización lee `paises.geojson` con `pg_read_file` y extrae los
  atributos con funciones JSON. La clave primaria es `ADM0_A3`. Las geometrías no se guardan en
  la base: el cruce espacial lo hace el consumidor.
- **Razón**: una única copia del catálogo, sin fichero SQL generado que pueda desfasarse; la
  clave primaria hace que una carga con identificadores repetidos falle (FR-016).
  **Verificado**: 177 filas, 5 con `ISO_A3 = -99` que se guardan como nulo (Noruega, Francia,
  Chipre del Norte, Somalilandia y Kosovo), lo que confirma que `ADM0_A3` no es un código ISO.
- **Alternativas**: carga desde el consumidor (la API dependería de que el consumidor haya
  arrancado); script generador de `INSERT` (duplica el catálogo en el repositorio).

## R6. Ausencia de país

- **Decisión**: `country_id` nulo. «Sin país asignado» es un texto de presentación que ponen la
  API y el panel.
- **Razón**: lo pide el contrato (`null` para país desconocido) y la FAQ 20; una fila ficticia
  en la dimensión haría pasar por país lo que no lo es.
- **Alternativas**: fila centinela (es el diseño actual).

## R7. Dimensión de fecha

- **Decisión**: un día UTC por fila desde 1900-01-01 hasta 2035-12-31 (49.673 filas,
  **verificado**), generada en la inicialización.
- **Razón**: cubre el histórico obligatorio de 2025, el periodo actual y la ampliación prevista
  a todo el catálogo de USGS (que empieza en 1900) sin tocar el modelo.

## R8. Tipos de datos

- **Decisión**: tiempos en `timestamptz` (UTC, resolución de microsegundo, conserva los
  milisegundos de USGS); magnitud, profundidad y coordenadas en `double precision`; original en
  `jsonb`; anomalías señaladas en `text[]`.
- **Razón**: USGS publica valores como `1.9200000048`; un `numeric` con escala fija los
  alteraría. Restricciones `CHECK` impiden NaN e infinito (**verificado**) y coordenadas fuera
  de rango, y no imponen mínimo a magnitud ni profundidad.
- **Alternativas**: guardar además los milisegundos originales en columnas `bigint` (redundante:
  están en el original y se derivan sin pérdida).

## R9. Cuarentena idempotente

- **Decisión**: una fila por mensaje rechazado, con restricción única sobre topic, partición y
  offset, lista de códigos de motivo y el original como `jsonb` o como texto si no es JSON.
- **Razón**: reprocesar un mensaje tras un fallo no duplica el rechazo (FR-018). Un indicador
  `is_synthetic` separa los casos dañados a propósito.
- **Alternativas**: una fila por motivo (diseño actual; infla los recuentos y obliga a
  deduplicar al analizar).

## R10. Originales y retención

- **Decisión**: `extraction` registra cada consulta para siempre (es pequeña). `raw_payload`
  guarda el cuerpo comprimido una vez por huella de contenido y se purga a los 7 días
  (`RAW_PAYLOAD_RETENTION_DAYS`). Los ficheros del catálogo histórico viven en `data/`, fuera de
  Git, y en la base solo consta su huella y su ruta. La huella se calcula sobre la colección de
  eventos, no sobre la cabecera de la respuesta.
- **Razón**: la cabecera de USGS cambia en cada respuesta (`metadata.generated`), así que una
  huella del cuerpo completo nunca detectaría copias idénticas. Estimación: hasta 10.080
  consultas por semana, unos 40 kB comprimidos por cuerpo distinto, por debajo de 400 MB en el
  peor caso. Con los 30 días supuestos inicialmente serían más de 1,5 GB; por eso la spec se ha
  ajustado a 7 días. La versión original de cada evento se conserva además indefinidamente en
  el historial de versiones.
- **Alternativas**: guardar todos los cuerpos sin límite (crece sin control); no guardar cuerpos
  (incumple §5.2).

## R11. Índices candidatos y criterio de permanencia

- **Decisión**: se parte del mínimo y cada índice secundario debe ganarse el sitio en la
  medición (FR-027).

  | Índice | Consulta que debe mejorar | Estado inicial |
  |---|---|---|
  | PK `event_current(event_id)` | upsert por identificador | obligatorio |
  | PK `event_version(event_id, updated_at)` | versiones de un evento, unicidad de versión | obligatorio |
  | `event_current(event_time)` | intervalo temporal, ventanas horarias, últimas 24 h | candidato |
  | `event_current(country_id, event_time)` | filtro por país más intervalo | candidato |
  | `event_current(magnitude, event_time)` | `min_mag` sobre periodos largos | candidato |
  | BRIN sobre `event_time` | alternativa compacta para volúmenes grandes | solo se mide |
  | parcial sobre `extraction(requested_at)` con resultado correcto | `last_ingestion` | candidato |

- **Razón**: el índice redundante `ix_event_versions_external_id` del modelo anterior duplicaba
  la restricción única; no se repite el error. Lo que no mejore en el tamaño mayor se retira y
  se documenta.
- **Medición**: datos sintéticos en `bench` con 10.000, 100.000 y 1.000.000 de filas,
  `EXPLAIN (ANALYZE, BUFFERS)` sin y con índice, mediana de 5 ejecuciones, tamaño del índice.

## R12. Privilegios mínimos

- **Decisión**: tres roles. El propietario crea el modelo; `observatory_writer` (productor y
  consumidor) lee y escribe; `observatory_reader` (API) solo lee.
- **Razón**: la API es el único componente expuesto a Internet por el túnel. Con un rol de solo
  lectura, un fallo en la API no puede modificar ni borrar datos. Es además una decisión propia
  fácil de explicar en la defensa.
- **Alternativas**: un único usuario (diseño actual); es más simple pero deja el almacén
  expuesto a cualquier error de la capa pública.

## R13. Imágenes y versiones

- **Decisión**: `postgres:16.4`, `confluentinc/cp-kafka:7.7.1` en modo KRaft (ya en uso y
  funcionando), `python:3.11.10-slim-bookworm`, `ngrok/ngrok:3.18.4-alpine`. Todas las
  etiquetas existen en el registro (**verificado**).
- **Razón**: se abandona `postgis/postgis` porque ninguna consulta usa PostGIS; el enunciado
  pide PostgreSQL y el cruce espacial se hace en Python.
- **Dependencias Python**: cada servicio tiene un `requirements.in` con dependencias directas y
  un `requirements.txt` generado con todas las transitivas fijadas. Se eliminan
  `pydantic-settings`, `geoalchemy2` y `ngrok`, sin fijar y sin uso.

## R14. Red, puertos y túnel

- **Decisión**: Kafka con un único listener interno y sin puertos publicados; PostgreSQL sin
  puertos publicados; API publicada en `127.0.0.1:8000`. El túnel es un servicio `tunnel` bajo
  el perfil de Compose `tunnel`, que apunta a `http://api:8000`.
- **Razón**: FR-006 y FR-007. Con perfiles, `docker compose up --build -d` arranca exactamente
  los cinco servicios obligatorios y el túnel se activa con `--profile tunnel`.
- **Consecuencia**: las herramientas que antes entraban por `localhost:29092` o `localhost:5432`
  se ejecutan ahora dentro de la red de Compose (`docker compose exec` o el fichero de
  desarrollo).
- **Pendiente de comprobar al implementar**: sintaxis exacta del agente para el dominio
  reservado en la versión fijada (`--url` frente a `--domain`).

## R15. Creación de topics

- **Decisión**: productor y consumidor crean los topics al arrancar con el cliente de
  administración de `aiokafka`, de forma idempotente y con particiones y retención explícitas.
  La creación automática del broker se desactiva. Topics: `earthquakes.live`,
  `earthquakes.catalog` y `earthquakes.replay`, una partición cada uno, retención de 7 días.
- **Razón**: hoy los topics se crean dentro de la comprobación de salud de Kafka, que mezcla dos
  responsabilidades. Un contenedor de inicialización añadiría un sexto servicio al arranque.
- **Alternativas**: creación automática (los topics aparecerían con la configuración por
  defecto y sin control de retención).

## R16. Comprobaciones de salud y reintentos

- **Decisión**: PostgreSQL se considera sano cuando acepta conexiones TCP y existe el modelo;
  Kafka cuando responde a una consulta de versiones de API; la API cuando `GET /api/salud`
  responde; productor y consumidor mediante un fichero de latido que actualizan en cada ciclo
  correcto y que la comprobación exige reciente. Todos con `restart: unless-stopped` y
  reintentos con espera exponencial y tope.
- **Razón**: `pg_isready` por socket local da positivo durante la fase de inicialización, antes
  de que existan las tablas; por eso se comprueba por TCP y se consulta el modelo.

## R17. Código compartido y continuidad de los servicios

- **Decisión**: paquete `common/` con configuración, registro, reintentos, conexión a la base,
  creación de topics y latido, copiado en las tres imágenes. Se mantienen tres Dockerfile porque
  solo el consumidor necesita las bibliotecas geoespaciales. En esta funcionalidad la lógica
  actual de los servicios se adapta lo mínimo para escribir y leer el modelo nuevo; su
  comportamiento se rehace en las specs 003, 004 y 006.
- **Razón**: mantener un evento recorriendo todo el sistema después de cada funcionalidad (FAQ 6
  y 7) permite verificar el conjunto de forma continua.
- **Controlador de base de datos**: `asyncpg` pasa a ser el único controlador; la API ya lo usa
  y encaja con los bucles asíncronos de `aiokafka`. Productor y consumidor migran desde
  `psycopg2` al adaptar su capa de persistencia.

## R18. Pruebas

- **Decisión**: `pytest` ejecutado en un contenedor definido en `compose.dev.yaml`, contra una
  base temporal `observatory_test` creada con los mismos ficheros de inicialización. Se
  eliminan las pruebas que solo buscan texto en el código fuente.
- **Razón**: principio IX. Las pruebas del modelo ejercitan las restricciones reales y no tocan
  los datos del observatorio; el fichero de desarrollo mantiene `compose.yaml` con los cinco
  servicios y el túnel opcional, nada más.
