# Feature Specification: Streaming de sismos con ETL y consulta geoespacial

**Feature Branch**: `001-streaming-sismos-etl`

**Created**: 2026-11-09

**Status**: Draft

**Input**: User description: "Basado en la constitución actual, genera el documento de especificación funcional (spec). Enlaza la lógica de negocio con nuestra arquitectura de contenedores Docker detallando el productor, el consumidor ETL, la API FastAPI y la reproducción de históricos de 2025."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ingestar y validar sismos (Priority: P1)

Como responsable de datos, quiero que el sistema recoja periódicamente el feed
sísmico, valide cada evento y conserve tanto los datos aceptados como los rechazados
para disponer de un registro fiable y auditable.

**Why this priority**: Sin ingesta y validación no existe información disponible para
la consulta ni una base confiable para la demostración.

**Independent Test**: Publicar un conjunto de eventos válidos, inválidos y repetidos
y comprobar que los válidos se enriquecen y persisten, los inválidos aparecen en
cuarentena con su motivo y los repetidos no crean duplicados.

**Acceptance Scenarios**:

1. **Given** un feed GeoJSON accesible con features sísmicos, **When** se ejecuta el
   ciclo de ingesta, **Then** cada feature se publica como un evento JSON en
   `terremotos_raw`.
2. **Given** un evento con magnitud nula o coordenadas fuera de rango, **When** el
   consumidor lo procesa, **Then** no se incorpora al conjunto de eventos válidos y
   se registra en `cuarentena` con un motivo concreto.
3. **Given** un evento válido con coordenadas terrestres, **When** se procesa,
   **Then** se persiste enriquecido con país, continente y subregión.
4. **Given** un evento marítimo válido, **When** se procesa, **Then** se persiste con
   país `Sin país asignado` sin imputar el país más cercano.
5. **Given** el mismo `id` recibido de nuevo, **When** su `updated` no es posterior
   al ya persistido, **Then** el sistema no duplica ni reemplaza el registro actual.
6. **Given** un evento cuyo guardado en base de datos falla, **When** termina el
   intento de procesamiento, **Then** el offset no se confirma y el evento puede
   reintentarse.

---

### User Story 2 - Consultar eventos y estadísticas (Priority: P2)

Como usuario del observatorio, quiero consultar sismos filtrando por país, fecha y
magnitud, y visualizar estadísticas temporales y por país para interpretar la
actividad sísmica.

**Why this priority**: Convierte el flujo de datos en información útil para el
frontend y la presentación.

**Independent Test**: Con una colección conocida de eventos persistidos, solicitar
cada consulta con y sin filtros y comparar resultados, conteos y geometrías con los
valores esperados.

**Acceptance Scenarios**:

1. **Given** eventos persistidos, **When** el usuario solicita eventos sin filtros,
   **Then** recibe la lista disponible con sus atributos y ubicación.
2. **Given** filtros de país, intervalo temporal y magnitud, **When** el usuario
   solicita eventos, **Then** solo recibe los registros que cumplen todos los
   filtros indicados.
3. **Given** eventos con coordenadas, **When** el frontend solicita una respuesta
   geográfica, **Then** recibe un GeoJSON válido con geometrías Point y propiedades
   del evento.
4. **Given** eventos persistidos, **When** el usuario solicita estadísticas por
   país o timeline, **Then** recibe conteos agrupados por país o periodo temporal.
5. **Given** filtros inválidos o fechas incompatibles, **When** se realiza la
   consulta, **Then** se devuelve un error claro sin ejecutar una consulta ambigua.

---

### User Story 3 - Reproducir un histórico para la presentación (Priority: P3)

Como responsable de la demostración, quiero inyectar rápidamente el histórico de
2025 en un canal separado para comprobar el consumidor bajo carga sin depender del
ritmo normal del feed.

**Why this priority**: Permite validar y demostrar el pipeline de forma repetible,
sin alterar el canal de producción.

**Independent Test**: Cargar un histórico de 2025 en `terremotos_replay`, consumirlo
a velocidad acelerada y comprobar las mismas reglas de validación, enriquecimiento,
persistencia, cuarentena e idempotencia.

**Acceptance Scenarios**:

1. **Given** un histórico válido de 2025, **When** se inyecta en
   `terremotos_replay`, **Then** el consumidor puede procesarlo a mayor velocidad
   que el ciclo periódico normal.
2. **Given** registros inválidos y repetidos en el histórico, **When** se reproduce,
   **Then** se aplican las mismas reglas de cuarentena e idempotencia que en
   `terremotos_raw`.
3. **Given** que finaliza la reproducción, **When** se consultan los resultados,
   **Then** los conteos persistidos y los eventos en cuarentena son trazables al
   histórico utilizado.

### Edge Cases

- Feed inaccesible, vacío o con JSON/GeoJSON malformado: el ciclo informa el error y
  no confirma eventos inexistentes ni borra datos previamente válidos.
- Feature sin `id`, `updated`, geometría o propiedades mínimas: se envía a
  cuarentena indicando el campo ausente.
- Magnitud no numérica, nula o fuera del rango aceptado: se envía a cuarentena.
- Longitud fuera de `[-180, 180]`, latitud fuera de `[-90, 90]` o coordenada no
  finita: se envía a cuarentena.
- Coordenada que no interseca ningún polígono terrestre: se clasifica como `Sin país
  asignado`, sin aproximación al país vecino.
- Evento posterior al registrado con el mismo `id`: reemplaza el registro solo si
  `updated` es más reciente.
- Caída de PostgreSQL, Kafka o del enriquecimiento espacial: no se confirma el
  offset antes de completar la operación requerida y el fallo queda observable.
- Consulta sin resultados: devuelve una colección vacía válida, no un error.
- Reproducción simultánea con ingesta normal: los canales se mantienen identificables
  y no se mezclan silenciosamente.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El contenedor Productor MUST ejecutar un ciclo configurable, con
  intervalo predeterminado de 60 segundos, para obtener el GeoJSON de USGS
  (`earthquakes_feed.geojson`).
- **FR-002**: El Productor MUST extraer cada `feature`, conservar sus atributos y
  geometría, convertirlo a JSON y publicarlo en `terremotos_raw`.
- **FR-003**: El Consumidor MUST escuchar `terremotos_raw` y
  `terremotos_replay`, identificando el origen de cada evento.
- **FR-004**: El Consumidor MUST validar que la magnitud no sea nula, sea numérica y
  esté dentro del rango aceptado, y que las coordenadas sean numéricas, finitas y
  estén dentro de sus rangos geográficos.
- **FR-005**: Todo evento que incumpla una validación MUST insertarse en `cuarentena`
  con el payload recibido, fecha de procesamiento y motivo específico, sin
  descartarse silenciosamente.
- **FR-006**: Para cada evento válido, el Consumidor MUST obtener país, continente y
  subregión mediante el cruce Point in Polygon con `paises.geojson` basado en
  Natural Earth.
- **FR-007**: El Consumidor MUST asignar exactamente `Sin país asignado` a eventos
  marítimos y MUST NOT imputarles el país más cercano.
- **FR-008**: El Consumidor MUST persistir eventos válidos con un upsert por `id`,
  reemplazando el registro existente solo cuando el `updated` recibido sea más
  reciente.
- **FR-009**: El guardado del evento y la confirmación de su offset MUST respetar una
  transacción: el offset solo se confirma después del commit exitoso en PostgreSQL.
- **FR-010**: El sistema MUST procesar con semántica at-least-once y permitir
  reintentos sin crear duplicidades.
- **FR-011**: La API MUST exponer `GET /eventos` con filtros combinables de país,
  fecha inicial, fecha final y magnitud, y MUST ofrecer GeoJSON cuando se solicite
  una respuesta geográfica.
- **FR-012**: La API MUST exponer `GET /estadisticas/paises` con el conteo de
  eventos agrupado por país.
- **FR-013**: La API MUST exponer `GET /estadisticas/timeline` con el conteo de
  eventos agrupado por periodo temporal.
- **FR-014**: La API MUST devolver errores claros para parámetros inválidos y
  respuestas vacías válidas cuando no existan coincidencias.
- **FR-015**: El flujo de reproducción MUST permitir cargar un histórico de 2025 en
  `terremotos_replay` y procesarlo a una velocidad configurable superior al ciclo
  periódico del Productor.
- **FR-016**: El backend unificado MUST ejecutarse exclusivamente mediante
  `docker compose up --build -d`, con los cinco servicios locales definidos por el
  sistema y sin dependencias de servicios Cloud.
- **FR-017**: La solución MUST respetar los límites constitucionales: no usar Spark,
  Flink, Kubernetes, Streamlit ni generar informes automáticos de calidad.
- **FR-018**: El WAF MUST clasificar como `Frescura` y enviar a cuarentena todo
  evento cuyo `time` supere el instante actual en más de 300 segundos. Para
  `terremotos_raw`, también MUST rechazar eventos con más de 7 días de antigüedad;
  `terremotos_replay` MUST aceptar históricos de 2025, manteniendo el rechazo de
  timestamps futuros.
- **FR-019**: La suite de integración MUST incluir una prueba E2E real que publique
  simultáneamente en `terremotos_raw` y `terremotos_replay`, consulte la API HTTP
  real y verifique GeoJSON y ambas respuestas estadísticas.

### Key Entities *(include if feature involves data)*

- **Evento sísmico**: observación con `id`, `updated`, magnitud, fecha, coordenadas,
  propiedades originales y clasificación geográfica enriquecida.
- **Evento en cuarentena**: observación inválida o anómala con payload original,
  motivo, origen y momento del rechazo.
- **Clasificación geográfica**: país, continente y subregión derivados de la
  intersección espacial; para el mar, país `Sin país asignado`.
- **Consulta estadística**: agrupación de eventos por país o periodo temporal para
  análisis y visualización.
- **Lote de reproducción**: histórico fechado en 2025 usado para pruebas aceleradas,
  separado de la ingesta normal.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En una ejecución de demostración, al menos el 99% de los eventos
  válidos del feed se encuentran disponibles para consulta tras completar su ciclo
  de procesamiento.
- **SC-002**: El 100% de los eventos con magnitud nula o coordenadas fuera de rango
  aparece en cuarentena con un motivo específico y verificable.
- **SC-003**: Reprocesar el mismo lote no incrementa el número de eventos únicos por
  `id`; un evento solo cambia cuando su `updated` es más reciente.
- **SC-004**: El 100% de los eventos marítimos consultados muestra país
  `Sin país asignado` y ninguno se atribuye al país más cercano.
- **SC-005**: Al menos el 95% de las consultas válidas de eventos y estadísticas
  devuelve resultados en un tiempo que permita interacción fluida durante la
  presentación (máximo 2 segundos con el dataset de demostración).
- **SC-006**: El histórico completo de 2025 puede reproducirse a una velocidad al
  menos 10 veces superior al intervalo normal de 60 segundos, sin perder eventos
  válidos ni ocultar rechazos.
- **SC-007**: Una persona que use el frontend puede aplicar país, fecha y magnitud,
  interpretar el resultado geográfico y consultar ambas estadísticas sin asistencia
  técnica en una prueba de aceptación.
- **SC-008**: Con el stack local activo, la prueba E2E real obtiene HTTP 200 para
  GeoJSON, países y timeline, y encuentra eventos procesados desde ambos topics.

**Estado de verificación E2E: [OK PASS]** con el stack local activo; la prueba real
confirma ambos topics, GeoJSON y las dos respuestas estadísticas.

## Assumptions

- El feed de USGS entrega un GeoJSON con `feature`, identificador estable, fecha de
  actualización y coordenadas compatibles con el modelo del observatorio.
- El archivo `paises.geojson` contiene geometrías Natural Earth y atributos
  suficientes para país, continente y subregión.
- El intervalo predeterminado del Productor es 60 segundos y puede configurarse
  para pruebas sin cambiar las reglas de negocio.
- La presentación dispone de un histórico de 2025 preparado y de permisos para
  publicarlo en `terremotos_replay`.
- La interfaz Angular consume la API a través del túnel ngrok y el frontend se
  publica en Netlify; la funcionalidad de autenticación no forma parte de esta
  especificación.
- El dataset de demostración es suficientemente pequeño para cumplir el objetivo de
  2 segundos y no representa un objetivo de capacidad productiva ilimitada.
- La arquitectura de cinco servicios locales y sus nombres concretos se mantienen
  alineados con `compose.yaml`; cualquier cambio de topología requiere una
  enmienda constitucional.
