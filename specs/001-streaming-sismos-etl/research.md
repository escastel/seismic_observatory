# Research: Streaming de sismos con ETL y consulta geoespacial

## Decisión 1: cinco servicios de negocio y arranque reproducible

- **Decision**: Productor, Consumidor, API, Kafka y PostgreSQL se orquestan en
  `compose.yaml` con redes internas, healthchecks y volúmenes para PostgreSQL.
- **Rationale**: Aísla ciclos de ingesta, procesamiento y consulta sin añadir
  plataformas prohibidas. Los healthchecks evitan que los clientes arranquen antes
  de sus dependencias.
- **Alternatives considered**: Un proceso monolítico se rechazó porque mezcla
  escalado y fallos de responsabilidades distintas; Kubernetes se rechaza por límite
  constitucional.

## Decisión 2: coordinación de PostgreSQL y Kafka

- **Decision**: El consumidor procesa un mensaje, abre una transacción PostgreSQL,
  ejecuta cuarentena o upsert, hace commit de DB y solo entonces llama al commit
  manual del offset Kafka. Un reinicio entre ambos commits puede reprocesar el
  evento, por lo que el upsert debe ser idempotente.
- **Rationale**: Es la garantía exigida de at-least-once y evita confirmar datos no
  persistidos. La unicidad por `id` y la comparación de `updated` hacen seguro el
  reintento.
- **Alternatives considered**: Commit Kafka antes de DB se rechaza por pérdida
  potencial; una transacción distribuida se rechaza por complejidad y por no ser
  necesaria para el modelo idempotente local.

## Decisión 3: validación WAF y siete dimensiones de calidad

- **Decision**: Cada rechazo registra una dimensión normalizada: Completitud,
  Validez, Exactitud, Consistencia, Oportunidad, Unicidad o Frescura, además del
  motivo y payload.
- **Rationale**: Hace auditable la calidad y permite agrupar fallos sin descartar
  silenciosamente. Nulos se etiquetan como Completitud; coordenadas inválidas como
  Validez; duplicados obsoletos como Unicidad.
- **Alternatives considered**: Un mensaje libre sin dimensión se rechaza por no
  permitir análisis consistente; descartar se prohíbe constitucionalmente.

## Decisión 4: esquema dimensional e índices

- **Decision**: `fact_sismos` referencia `dim_geografia` y `dim_tiempo`; las
  dimensiones se resuelven por claves naturales/fechas y la fact conserva el `id`
  externo, `updated`, magnitud y coordenadas. Se crean índices B-Tree para
  `fact_sismos.event_time` y `dim_geografia.country`, además de unicidad por
  `external_id`.
- **Rationale**: Separa hechos medibles de atributos reutilizables y permite filtros
  O(log n) en las columnas solicitadas.
- **Alternatives considered**: Una tabla plana simplifica el primer prototipo pero
  no satisface el modelo Star Schema solicitado; índices hash no son la opción
  general para rangos temporales.

## Decisión 5: GeoPandas y sismos marítimos

- **Decision**: Se usa Point in Polygon contra Natural Earth; si no hay intersección,
  país es exactamente `Sin país asignado` y continente/subregión quedan explícitos
  como no asignados.
- **Rationale**: Evita imputación geográfica falsa y conserva la semántica
  marítima exigida.
- **Alternatives considered**: Vecino más cercano se rechaza porque inventa país;
  geocodificación externa se rechaza por dependencia Cloud y falta de
  reproducibilidad.

## Decisión 6: API y CORS

- **Decision**: FastAPI ofrece filtros tipados, respuestas JSON y GeoJSON
  `FeatureCollection`; CORS se configura por variable de entorno, con `*` para demo
  local o lista explícita de Netlify/ngrok.
- **Rationale**: Mantiene contrato claro para Angular y evita bloqueos del navegador
  en la publicación remota.
- **Alternatives considered**: CORS solo en frontend no controla la política del
  navegador; GraphQL no es necesario para los tres endpoints definidos.

## Decisión 7: replay acelerado

- **Decision**: Un script de soporte publica JSONL de 2025 en
  `terremotos_replay` con `--rate` configurable; el mismo consumidor atiende ambos
  topics y conserva `source_topic`.
- **Rationale**: Reproduce carga sin alterar el ritmo de USGS y ejercita las mismas
  reglas.
- **Alternatives considered**: Inyectar en `terremotos_raw` se rechaza porque mezcla
  demostración con producción y dificulta la trazabilidad.
