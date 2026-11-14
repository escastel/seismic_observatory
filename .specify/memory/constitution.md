# Observatorio Sísmico Constitution

## Core Principles

### I. Arquitectura local reproducible y superficie mínima
Productor Python (aiokafka), Apache Kafka, consumidor Python (aiokafka), PostgreSQL y API FastAPI
MUST ejecutarse como cinco servicios separados de Docker Compose y arrancar juntos con
`docker compose up --build -d` desde un clon limpio más un `.env` derivado de `.env.example`.
Cada servicio MUST declarar comprobación de salud y reintentos de conexión; el orden de arranque
no se considera garantía de disponibilidad. Los datos MUST persistir en volúmenes y Kafka MUST
tener una retención limitada y documentada. Las dependencias Python y Node MUST estar fijadas a
versión exacta. Solo la API de consulta se expone fuera de la red de Compose; Kafka y PostgreSQL
MUST NOT publicarse por el túnel. El productor y el consumidor MUST seguir funcionando con el
panel cerrado.
**Razón**: el evaluador debe poder levantar el sistema sin adivinar pasos y sin exponer
almacenamiento ni broker.

### II. Al menos una vez con escritura idempotente y versionada
El productor MUST esperar la confirmación de Kafka antes de marcar una versión como publicada y
MUST usar el identificador del evento como clave del mensaje. El consumidor MUST confirmar el
offset únicamente después del commit de PostgreSQL, y un fallo de procesamiento MUST NOT permitir
que el offset avance por encima del mensaje fallido. El estado actual tiene una fila por
`event_id` y solo se actualiza si el `updated` recibido es estrictamente posterior; cada versión
observada se conserva una vez por `(event_id, updated)`. Reprocesar cualquier mensaje MUST dejar
los recuentos intactos. Un consumidor nuevo MUST empezar desde el principio del topic, no desde
el final. No se exige transacción distribuida Kafka–PostgreSQL.
**Razón**: la secuencia primera versión, repetición, revisión, versión antigua tardía y reinicio
es el núcleo evaluado del modelado.

### III. Calidad con reglas explícitas: conservar, señalar o poner en cuarentena
Cada regla de validación y transformación MUST estar escrita, tener un código de motivo estable
y registrar a cuántos registros afecta. Los nulos MUST NOT rellenarse con cero ni con valores
inventados: una magnitud o profundidad ausente se conserva como `NULL`, se muestra como ND, se
excluye de los cálculos que la necesitan y se contabiliza aparte. Una magnitud negativa o una
profundidad negativa MUST NOT rechazarse por serlo: se conservan y, si procede, se señalan como
anomalía. Solo va a cuarentena lo que no puede tratarse (JSON ilegible, falta de `id`, `time` o
`updated`, geometría que no sea un `Point` con longitud y latitud finitas y en rango), siempre
con motivo y referencia al original. Los tipos distintos de `earthquake` se excluyen del
análisis conservando el motivo de exclusión. Un registro defectuoso MUST NOT perderse en
silencio ni bloquear indefinidamente la cola. Los casos de prueba dañados a propósito MUST
quedar separados e identificados como sintéticos. Las fechas se convierten a UTC conservando el
valor original y separando tiempo de ocurrencia, actualización en USGS e ingesta.
**Razón**: el enunciado evalúa decisiones justificadas sobre los datos, no la cantidad de
rechazos.

### IV. Integración espacial verificable
El país MUST obtenerse con una operación de punto dentro de polígono sobre la copia entregada de
Natural Earth, en WGS84 (EPSG:4326), nunca a partir del texto de `place`. `ADM0_A3` es el
identificador de la entidad tras comprobar su unicidad y MUST NOT tratarse como código ISO
oficial. Un punto sin polígono queda con país nulo y se presenta como «Sin país asignado»; MUST
NOT atribuirse al país más cercano ni clasificarse como error, y MUST permanecer en el análisis.
La regla para puntos sobre una frontera o con varias coincidencias MUST estar documentada y ser
determinista.
**Razón**: es la segunda fuente que convierte el proyecto en una integración y no en una copia
de USGS.

### V. Conservación del original y procedencia
El GeoJSON original y sus metadatos de extracción MUST conservarse antes de transformar, sin
almacenar indefinidamente copias idénticas y con una retención definida. Toda consulta al feed o
al catálogo histórico MUST quedar registrada con URL o parámetros, fecha de extracción, resultado
y número de registros. Un exceso sobre el máximo del catálogo MUST resolverse subdividiendo el
intervalo, nunca truncando en silencio, y los eventos compartidos entre intervalos MUST
deduplicarse. Un evento que deja de aparecer en la ventana de 24 horas MUST NOT borrarse. Los
conjuntos descargables grandes MUST NOT versionarse en Git: se guardan en una ubicación
documentada con un procedimiento para regenerarlos.
**Razón**: sostiene el criterio de extracción y permite reconstruir qué datos se usaron.

### VI. Aislamiento estricto de la reproducción
La reproducción histórica MUST circular por Kafka en un topic propio y persistirse en un esquema
o tablas separados de los datos reales, reutilizando sin bifurcar el código de procesamiento del
consumidor. MUST conservar el tiempo original del evento y añadir el tiempo de reproducción;
MUST NOT alterar fechas para que aparezcan en una vista reciente. Toda respuesta de la API y
toda vista del panel que muestre datos de reproducción MUST identificarse como «REPRODUCCIÓN».
Los datos sintéticos de pruebas de escala MUST quedar fuera del análisis real.
**Razón**: mezclar reproducción y actualidad invalida las conclusiones y la comparación
histórica.

### VII. Analítica derivada del estado actual y comparación equivalente
Los recuentos, ventanas y distribuciones MUST calcularse desde la tabla de estado actual; MUST
NOT mantenerse contadores incrementados por mensaje. Las ventanas son fijas de una hora UTC
sobre el tiempo de ocurrencia, con extremo final excluido. Mapa, tabla y estadísticas MUST
aplicar los mismos filtros. La comparación histórica MUST usar los mismos filtros de magnitud,
tipo y ámbito en ambos periodos, MUST incluir en el denominador los días sin eventos y MUST
mostrar ND cuando la media sea cero. Todo resultado MUST indicar periodo, filtros, unidad y
registros sin valor. Las conclusiones MUST NOT presentarse como predicción ni como evaluación de
riesgo, y MUST advertir de que el periodo reciente puede estar incompleto.
**Razón**: es lo que distingue un análisis con conclusiones de una colección de gráficos.

### VIII. El contrato de la API es la fuente de verdad
La API MUST cumplir `resources/observatorio-sismico/CONTRATO-API.md`: `GET /api/eventos` devuelve
un `FeatureCollection` con una sola versión actual por evento, tiempos en milisegundos Unix UTC,
`null` y nunca NaN o Infinity, últimas 24 horas por defecto, filtros `start` (inclusive), `end`
(exclusive), `min_mag` y `country_id`, y truncado explícito con total y paginación. `GET
/api/salud` y `GET /api/estadisticas` completan el contrato. `last_ingestion` significa última
consulta correcta a USGS, no última fila escrita. Un fallo de la base MUST producir un error
explícito, nunca cero eventos como resultado válido. La API solo lee datos ya procesados y MUST
NOT consultar USGS. CORS MUST autorizar el origen exacto de Netlify y el de desarrollo, con
métodos GET y OPTIONS y la cabecera `ngrok-skip-browser-warning`; CORS no es autenticación. El
panel MUST distinguir última lectura del panel, generación de la respuesta y última ingesta, y
MUST avisar de datos desactualizados o de backend inaccesible conservando la última lectura
identificada como tal.
**Razón**: frontend y backend se desarrollan contra el mismo documento entregado por el
profesor.

### IX. Evidencia ejecutada y costes sin beneficios inventados
Una prueba de aceptación solo se declara superada después de ejecutarla y guardar resultado
esperado, resultado observado y evidencia repetible; MUST NOT darse por superada porque el
comportamiento esté programado. Las pruebas automáticas MUST comprobar comportamiento, no la
presencia de texto en el código fuente. El apartado de calidad vive en la memoria o en un
notebook, con consultas o código, resultados antes y después, y conjunto y denominador
explícitos; MUST NOT sumarse incidencias que pueden solaparse. Las mediciones de tiempo y
memoria MUST cubrir al menos tres tamaños de entrada e indicar equipo y procedimiento. Los
costes MUST distinguir valores medidos de supuestos y MUST NOT inventar beneficios económicos;
un ROI solo se estima si se define un beneficio medible y justificable. No se exige generar
informes de calidad automáticos ni un panel de calidad.
**Razón**: la guía de entregables valora que las evidencias sean comprobables, no la extensión
de los documentos.

## Stack Tecnológico y Límites

Componentes permitidos: Python con `aiokafka` para productor y consumidor, GeoPandas/Shapely para
la integración espacial, Apache Kafka, PostgreSQL, FastAPI, Docker Compose, Angular con Leaflet
partiendo del frontend entregado, Netlify para publicar la SPA y ngrok para el túnel HTTPS.

- ngrok se ejecuta como agente en el equipo o como contenedor adicional opcional de la misma red
  de Compose; no forma parte de los cinco servicios obligatorios y MUST NOT ejecutarse dentro
  del proceso de la API. La API atiende HTTP en `0.0.0.0:8000` dentro del contenedor y MUST NOT
  instalar certificados.
- Si la API se publica en el host, se enlaza a `127.0.0.1`.
- El authtoken de ngrok y cualquier credencial MUST NOT estar en Git ni en el frontend;
  `.env.example` no contiene secretos.
- Quedan fuera de alcance Spark, Flink, Kubernetes, aprendizaje automático y servidores cloud
  permanentes. Las ventanas se calculan con Python y SQL.
- El panel consulta la API propia cada 60 segundos y nunca USGS; el productor consulta USGS por
  su cuenta cada 60 segundos aproximadamente.
- Una biblioteca nueva solo se añade si resuelve un requisito del enunciado y queda fijada.

### Idioma y repositorio público

- El código y todo fichero o carpeta nuevos MUST escribirse en inglés: identificadores, tablas,
  columnas, topics, variables de entorno, comentarios de código, nombres de ficheros y de
  directorios, incluidos los de `specs/` y `docs/`.
- La documentación MUST redactarse en español: especificaciones, planes, memoria, README,
  diccionario de datos y textos visibles del panel.
- Los ficheros anteriores a esta regla no se renombran salvo que se rehagan.
- El repositorio es público. Antes de versionar cualquier fichero MUST comprobarse que no
  contiene credenciales, tokens, datos locales ni material de terceros sin permiso de
  redistribución, y `.gitignore` MUST actualizarse en el mismo cambio. Del material del
  profesor solo se publican el contrato de la API y las notas de fuentes, licencias y
  validación del paquete de apoyo; el enunciado, las FAQ y la guía se mantienen en local.

## Flujo de Desarrollo y Calidad

El trabajo sigue Spec-Driven Development: constitución, especificación, clarificación, plan,
tareas e implementación, una funcionalidad cada vez. Ninguna funcionalidad se implementa sin
especificación y plan aprobados. Cada especificación MUST trazar sus requisitos a apartados del
enunciado y a la prueba de aceptación que los evidencia.

Todo cambio que afecte al consumidor, al modelo de datos, a la topología de servicios, a los
contratos o a la analítica MUST revisarse contra los principios II, III, VI y VII, y MUST
comprobarse con el stack levantado mediante `docker compose up --build -d`.

El objetivo de calidad del proyecto es el nivel Sobresaliente de la rúbrica en sus cinco
criterios: extracción con análisis de tipos, calidad completa con acciones, modelo optimizado
con índices justificados por medición, análisis con conclusiones fundamentadas y reflexión con
propuestas. La complejidad de infraestructura adicional no aporta nota y MUST justificarse.

La entrega se organiza en `README.md` (arranque y demostración), `docs/report.md` o un notebook
(datos, calidad, modelo, análisis, mediciones, costes y decisiones), `docs/evidence/` y el SQL
de creación de tablas e índices. La memoria MUST distinguir el material de apoyo reutilizado del
desarrollado.

## Governance

Esta constitución prevalece sobre prácticas locales y sobre especificaciones anteriores que la
contradigan. Las fuentes normativas, por orden de precedencia, son: `resources/enunciado.md` y su
rúbrica (copia local, no publicada), `resources/observatorio-sismico/CONTRATO-API.md`, las FAQ
y la guía de entregables (que
aclaran sin añadir requisitos) y esta constitución. Si un principio contradice el enunciado,
prevalece el enunciado y la constitución MUST enmendarse.

Toda enmienda modifica este archivo mediante un cambio revisable que describa su impacto en
principios, stack, datos, contratos y pruebas, y requiere la aprobación explícita de la
responsable del proyecto. Las especificaciones y planes afectados MUST actualizarse o marcarse
como obsoletos en el mismo cambio.

El versionado es semántico: MAJOR al eliminar o redefinir de forma incompatible un principio o
límite; MINOR al añadir un principio, sección o requisito material; PATCH para aclaraciones sin
cambio de significado. Cada plan MUST incluir una comprobación de cumplimiento constitucional
antes del diseño y otra después, y cualquier excepción MUST quedar justificada por escrito.

**Version**: 2.1.0 | **Ratified**: 2026-11-09 | **Last Amended**: 2026-11-14
