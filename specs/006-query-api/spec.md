# Feature Specification: API de consulta conforme al contrato

**Feature Branch**: `006-query-api`

**Created**: 2026-11-16

**Status**: Draft

**Input**: User description: "Spec 006: API de consulta conforme al contrato, con lectura de datos reales y de reproducción, sobre la plataforma (002), la ingesta (003), el consumidor (004) y la reproducción (005). Objetivo: que la API cumpla `resources/observatorio-sismico/CONTRATO-API.md` (principio VIII, que esta spec cierra) y que todo dato de reproducción salga identificado como «REPRODUCCIÓN» sin mezclarse nunca con los datos reales (principio VI; enunciado §8, §9 y §11; FAQ 25 a 30 y 32). La API heredada de la spec 001 se revisa y ajusta, no se reescribe sin motivo."

**Depende de**: `specs/002-platform-data-model` (estado actual por evento, esquema `replay`,
registro de extracciones), `specs/003-usgs-ingestion` (consultas a USGS registradas en
`core.extraction`), `specs/004-consumer-quality` (reglas de calidad y convención de datos
sintéticos) y `specs/005-historical-replay` (datos de reproducción con `replayed_at`).

**Trazabilidad**: `CONTRATO-API.md`, constitución principios VI, VII y VIII, enunciado §8, §9,
§10 y §11, FAQ 25 a 30 y 32.

**Divergencias detectadas en la API heredada** (punto de partida, no requisitos): la lista de
eventos devuelve por defecto un JSON propio y solo con `format=geojson` una `FeatureCollection`;
`last_ingestion` es el último `ingested_at` escrito y no la última consulta correcta a USGS;
`metadata.mode` está fijado a «live»; las agregaciones son por día, semana y mes y no por ventana
de una hora UTC; la ventana por defecto de 24 horas no sirve para datos de 2025.

**Prueba de aceptación del enunciado (§11) que sostiene**: «Reproducción histórica» (parte de
datos: la API identifica la reproducción y los datos reales no cambian) y las pruebas de
consulta del panel (spec 007), que consumirá esta API.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consultar los eventos con un formato único y conforme al contrato (Priority: P1)

Como consumidor de la API (el panel de la spec 007 o una persona con un cliente HTTP), quiero
pedir los eventos con filtros de tiempo, magnitud y país y recibir siempre la misma estructura
con su metadatos, para pintarlos en el mapa y saber con qué datos y con qué frescura se ha
construido la respuesta.

**Why this priority**: es el contrato central y el dato que sostiene el mapa; sin él nada más
es utilizable.

**Independent Test**: con datos reales cargados, pedir eventos sin parámetros, con cada filtro y
con combinaciones, y comprobar estructura, orden de coordenadas, tiempos, nulos y metadatos
contra el contrato.

**Acceptance Scenarios**:

1. **Given** datos reales, **When** se piden eventos sin parámetros, **Then** la respuesta es
   siempre una colección de puntos geográficos con `metadata` (instante de generación, última
   ingesta, modo, número devuelto, indicador de truncado y total completo) y solo contiene
   terremotos de las últimas 24 horas por tiempo de ocurrencia.
2. **Given** un evento con varias versiones recibidas, **When** se consulta, **Then** aparece
   una sola vez, con su versión vigente.
3. **Given** los filtros de inicio (inclusivo), fin (exclusivo), magnitud mínima y país,
   **When** se combinan, **Then** el resultado cumple todos; un evento exactamente en el
   instante de inicio entra y uno exactamente en el de fin no.
4. **Given** un evento con magnitud nula, **When** se filtra por magnitud mínima, **Then** no
   cumple el filtro y se contabiliza aparte en los metadatos; sin filtro de magnitud se devuelve
   con la magnitud en `null`.
5. **Given** una consulta sin resultados, **When** se responde, **Then** el código es 200 con
   la lista de elementos vacía, nunca un error.
6. **Given** un evento sin coordenadas válidas, **When** se consulta, **Then** no aparece como
   punto (ninguna geometría inválida) y el hecho queda reflejado en los metadatos.
7. **Given** cualquier respuesta, **When** se inspecciona, **Then** los tiempos son
   milisegundos Unix UTC, las coordenadas son [longitud, latitud, profundidad] y los valores
   ausentes son `null`, nunca NaN ni infinito.
8. **Given** datos sintéticos presentes en la base, **When** se consulta en modo real, **Then**
   no aparecen jamás.

---

### User Story 2 - Consultar la reproducción identificada y aislada de lo real (Priority: P1)

Como persona que defiende el proyecto, quiero pedir los mismos datos en modo reproducción y que
cada respuesta diga sin ambigüedad que es «REPRODUCCIÓN», para demostrar el sistema sin
terremotos reales sin que nadie confunda lo reproducido con lo real.

**Why this priority**: es el riesgo de integridad más grave del proyecto (principio VI) y la
parte de datos de la prueba «Reproducción histórica».

**Independent Test**: registrar los conteos de la API en modo real, ejecutar una reproducción,
repetir los conteos y comparar; consultar en modo reproducción y comprobar etiquetas y datos.

**Acceptance Scenarios**:

1. **Given** el parámetro de modo con valor `replay`, **When** se piden eventos, **Then** solo
   se leen datos del espacio de reproducción, `metadata.mode` es «replay», `metadata` incluye la
   etiqueta explícita «REPRODUCCIÓN» y cada elemento lleva `replayed_at` en sus propiedades.
2. **Given** modo reproducción sin filtros de tiempo, **When** se consulta, **Then** no se aplica
   la ventana de 24 horas (los datos son históricos), pero sí los filtros indicados y la
   paginación.
3. **Given** modo reproducción, **When** se consulta, **Then** `last_ingestion` sigue siendo la
   última consulta correcta a USGS (real) y se añade el último `replayed_at`.
4. **Given** el modo omitido, **When** se consulta, **Then** se comporta como modo real.
5. **Given** una reproducción de miles de eventos, **When** termina, **Then** los conteos de
   la API en modo real son idénticos a los de antes, y un identificador presente en ambos
   espacios se devuelve en cada modo con sus valores propios.
6. **Given** datos sintéticos de la reproducción, **When** se consulta en modo reproducción,
   **Then** se distinguen del resto y pueden excluirse con un parámetro.
7. **Given** un valor de modo desconocido, **When** se consulta, **Then** se rechaza con un
   error de validación y mensaje útil, sin elegir un modo por defecto en silencio.

---

### User Story 3 - Conocer el estado del sistema y la frescura de los datos (Priority: P1)

Como consumidor de la API y como operador, quiero un estado de salud que diga si la API y su
base funcionan y cuándo fue la última ingesta correcta, para distinguir «no hay terremotos» de
«el sistema está parado».

**Why this priority**: una API que responde «cero eventos» cuando la base está caída o la
ingesta lleva horas parada invalida cualquier conclusión (§8).

**Independent Test**: consultar la salud con el sistema sano, con la base detenida y con la
ingesta parada, y comprobar que el estado y la fecha reflejan cada situación.

**Acceptance Scenarios**:

1. **Given** el sistema sano, **When** se consulta la salud, **Then** informa del estado de la
   API y de la fecha de la última consulta correcta a USGS registrada (no de la última fila
   escrita), sin credenciales ni datos internos sensibles.
2. **Given** que la base falla, **When** se consulta la salud, **Then** responde con estado
   degradado explícito y nunca como si todo fuera bien.
3. **Given** que aún no hay ninguna consulta correcta registrada, **When** se consulta,
   **Then** la fecha de última ingesta es `null` y el estado lo refleja.
4. **Given** que la base falla, **When** se piden eventos o estadísticas, **Then** se responde
   con un error HTTP explícito y cuerpo JSON; jamás con cero eventos como resultado válido.

---

### User Story 4 - Estadísticas por ventana horaria, país y comparación histórica (Priority: P2)

Como analista, quiero conteos por ventana fija de una hora UTC, por país, distribuciones de
magnitud y profundidad y una comparación con el histórico, calculados siempre desde el estado
actual y con los mismos filtros que el mapa, para extraer conclusiones sin contradicciones con
lo que se ve en el mapa.

**Why this priority**: sostiene el análisis (spec 008) y las pruebas de revisión, pero depende
de que la consulta de eventos ya sea correcta.

**Independent Test**: con un conjunto con respuestas conocidas, comparar cada agregación con el
cálculo directo sobre el estado actual, antes y después de una revisión y de una versión antigua
tardía.

**Acceptance Scenarios**:

1. **Given** un periodo, **When** se piden conteos por hora, **Then** cada ventana es de una
   hora UTC fija sobre el tiempo del evento, con el extremo final excluido, y las horas sin
   eventos constan con cero.
2. **Given** eventos sin país, **When** se agrupa por país, **Then** aparecen bajo «Sin país
   asignado» como categoría válida, no como error.
3. **Given** los mismos filtros que en el mapa, **When** se piden estadísticas, **Then** el
   total coincide exactamente con los eventos que el mapa devolvería sin truncar.
4. **Given** una revisión que cambia magnitud, país o tiempo de un evento, **When** se
   recalculan, **Then** cambian las agregaciones afectadas; **Given** una versión antigua
   tardía, **Then** no las altera.
5. **Given** eventos con magnitud o profundidad nulas, **When** se calculan las
   distribuciones, **Then** esos registros se cuentan aparte, no se descartan en silencio ni se
   cuentan como cero.
6. **Given** la comparación histórica (por ejemplo, últimas 24 horas con magnitud ≥ 4 frente a
   la media diaria de 2025 con los mismos filtros), **When** se calcula, **Then** el
   denominador incluye los días sin eventos, devuelve «ND» si la media es cero e incluye el
   aviso de que el periodo reciente puede estar incompleto.
7. **Given** cada resultado, **When** se inspecciona, **Then** indica periodo, filtros
   aplicados, unidad y registros sin valor.
8. **Given** una selección cuyo total supera el máximo de puntos, **When** se piden
   estadísticas, **Then** se calculan sobre el total real o se rechazan con un aviso explícito,
   y nunca se ofrecen como globales sobre la muestra truncada.
9. **Given** modo reproducción, **When** se piden estadísticas, **Then** la respuesta se
   identifica como «REPRODUCCIÓN», nunca mezcla ambos espacios y permite excluir los sintéticos.

---

### User Story 5 - Respuestas acotadas y paginadas (Priority: P2)

Como consumidor, quiero que las respuestas grandes se acoten con un máximo documentado y se
puedan recorrer por páginas, para no bloquear el navegador y saber siempre si veo el total.

**Why this priority**: los datos de 2025 superan con mucho una colección pequeña; sin acotar, el
mapa se degrada.

**Independent Test**: consultar un periodo con más eventos que el máximo, comprobar el
indicador, el total y que recorrer todas las páginas devuelve cada evento exactamente una vez.

**Acceptance Scenarios**:

1. **Given** más eventos que el máximo, **When** se consulta, **Then** `truncated` es `true`,
   los metadatos incluyen el total completo y el modo de pedir la página siguiente.
2. **Given** la paginación, **When** se recorren todas las páginas, **Then** se obtiene cada
   evento exactamente una vez, en un orden estable, incluso con empates de tiempo.
3. **Given** menos eventos que el máximo, **When** se consulta, **Then** `truncated` es `false`
   y el total coincide con el número devuelto.

---

### User Story 6 - Acceso controlado y parámetros validados (Priority: P2)

Como operador, quiero que solo los orígenes previstos puedan llamar a la API desde un
navegador, que no exista ninguna ruta de administración y que los parámetros erróneos reciban un
mensaje claro, para exponerla por el túnel sin riesgos.

**Why this priority**: la API se publica a través de un túnel a un panel externo; un error de
acceso rompe el panel o expone el sistema.

**Independent Test**: lanzar peticiones con orígenes permitidos y no permitidos, parámetros
inválidos y comprobar las rutas expuestas.

**Acceptance Scenarios**:

1. **Given** el origen del panel publicado y el origen local de desarrollo, **When** llaman,
   **Then** reciben las cabeceras de acceso permitidas, con la cabecera de omisión de aviso del
   túnel aceptada; **Given** otro origen, **Then** no se le concede acceso.
2. **Given** métodos distintos de lectura (y de la comprobación previa del navegador),
   **When** se envían, **Then** se rechazan, y no se usan cookies ni credenciales.
3. **Given** parámetros inválidos (fecha mal formada, magnitud no numérica, rango invertido,
   modo desconocido, tamaño de página fuera de rango), **When** se envían, **Then** la respuesta
   es 422 con un mensaje que indica qué parámetro falla y por qué.
4. **Given** la API desplegada, **When** se revisan sus rutas, **Then** solo existen las del
   contrato; ninguna escribe datos, ninguna es de administración y la API no consulta nunca a
   USGS.
5. **Given** el despliegue local, **When** se revisa el puerto, **Then** solo es accesible
   desde el propio equipo.

---

### User Story 7 - Retirar o justificar lo heredado fuera del contrato (Priority: P3)

Como mantenedora, quiero saber qué alias y rutas heredados usa realmente el frontend entregado y
conservar solo lo imprescindible, para que la API tenga una superficie mínima y documentada.

**Why this priority**: reduce ambigüedad y superficie, pero no bloquea el contrato.

**Independent Test**: comprobar que cada alias o ruta heredada se ha retirado o está
documentado con su motivo de conservación.

**Acceptance Scenarios**:

1. **Given** los alias y rutas heredados (`date_from`, `date_to`, `min_magnitude`,
   `max_magnitude`, `country`, las rutas de estadísticas por país y por línea temporal, el
   formato alternativo `json`), **When** se revisa el frontend entregado, **Then** cada uno queda
   marcado como usado o no usado.
2. **Given** el resultado, **When** se cierra la funcionalidad, **Then** lo no usado se ha
   retirado, lo conservado está documentado con motivo y fecha prevista de retirada, y los
   clientes del contrato siguen funcionando.

---

### User Story 8 - Evidencia, rendimiento y documentación (Priority: P3)

Como persona que defiende el proyecto, quiero evidencia con el sistema real, medidas de latencia
y ejemplos de consulta, para poder demostrar y justificar el comportamiento de la API.

**Why this priority**: sin evidencia la funcionalidad no es evaluable (constitución).

**Independent Test**: seguir los ejemplos del README sobre el sistema levantado y revisar
`docs/evidence/006/`.

**Acceptance Scenarios**:

1. **Given** `docs/evidence/006/`, **When** se consulta, **Then** contiene resultado esperado y
   observado de: evento nuevo visible; mismo mensaje repetido sin aumentar el recuento; versión
   posterior que cambia datos y agregaciones; versión antigua tardía que no sustituye; magnitud
   nula conservada y contada; coordenadas inválidas sin punto; evento marítimo sin país dentro
   del análisis; truncado con total y paginación; base caída con error explícito; y
   reproducción identificada y aislada (conteos reales idénticos antes y después).
2. **Given** la medición de latencia, **When** se revisa, **Then** incluye al menos tres tamaños
   de resultado, el equipo y el procedimiento, y la justificación de la agregación por ventanas.
3. **Given** el README y `docs/report.md`, **When** se leen, **Then** hay ejemplos de consulta de
   cada endpoint y del modo reproducción, y un apartado con el contrato implementado, las
   decisiones y las desviaciones.

---

### Edge Cases

- Rango de tiempo invertido (inicio posterior o igual al fin): 422 con mensaje, no lista vacía.
- Evento con tiempo de ocurrencia en el futuro, o anterior al inicio del catálogo: se trata como
  cualquier otro; se refleja en los filtros, no se descarta.
- Evento sin país asignado dentro de un filtro por país: no cumple el filtro; sí aparece en el
  análisis sin filtro de país, bajo «Sin país asignado».
- Evento con profundidad nula o negativa: se devuelve con la profundidad conservada o `null`; las
  coordenadas siguen siendo un punto válido si longitud y latitud lo son.
- Coordenadas fuera de rango o ausentes: no hay punto; el evento no se devuelve como elemento
  geográfico y se contabiliza aparte, sin ocultar el hecho.
- Dos eventos con el mismo tiempo de ocurrencia a caballo de dos páginas: ninguno se pierde ni se
  repite.
- Espacio de reproducción vacío: 200 con lista vacía y etiqueta «REPRODUCCIÓN», no error.
- Base accesible pero sin ninguna extracción correcta: `last_ingestion` es `null`.
- Base lenta o con tiempo de espera agotado: error explícito, no lista vacía.
- Petición del mismo identificador en ambos modos: cada modo ve solo lo suyo.
- Revisión que cambia el país o el instante de un evento entre dos consultas consecutivas: la
  segunda consulta refleja el estado nuevo en mapa y estadísticas a la vez.
- Una reproducción en curso mientras se consultan datos reales: las respuestas reales no
  cambian por ello.
- Periodo del que solo hay datos parciales (el reciente): la comparación histórica lo avisa.

## Requirements *(mandatory)*

### Functional Requirements

**Eventos**

- **FR-001**: La consulta de eventos MUST devolver siempre una colección de puntos geográficos
  con `metadata` que incluya instante de generación, última ingesta, modo, número devuelto,
  indicador de truncado y total completo.
- **FR-002**: La consulta MUST devolver una sola versión vigente por evento, tiempos en
  milisegundos Unix UTC, coordenadas [longitud, latitud, profundidad] y `null` para valores
  ausentes; MUST NOT emitir NaN ni infinito.
- **FR-003**: Sin eventos, la respuesta MUST ser 200 con lista vacía.
- **FR-004**: Sin filtros de tiempo, en modo real, MUST devolver los terremotos de las últimas
  24 horas por tiempo de ocurrencia.
- **FR-005**: MUST admitir los filtros inicio (inclusivo), fin (exclusivo), magnitud mínima y
  país; la magnitud nula MUST NOT cumplir la magnitud mínima y MUST contabilizarse aparte en los
  metadatos.
- **FR-006**: MUST aplicar un máximo documentado de puntos por respuesta; al truncar MUST indicar
  `truncated: true`, el total completo y cómo pedir la página siguiente. La paginación MUST ser
  estable.
- **FR-007**: MUST NOT devolver ningún elemento sin geometría válida; los eventos sin
  coordenadas válidas MUST contabilizarse en los metadatos.
- **FR-008**: En modo real MUST leer solo el estado actual del esquema real y MUST NOT devolver
  eventos sintéticos ni de otro esquema.

**Reproducción**

- **FR-009**: MUST admitir el parámetro de modo (`live` o `replay`), por defecto `live`; un valor
  desconocido MUST rechazarse con error de validación.
- **FR-010**: En modo `replay` MUST leer solo el esquema de reproducción, MUST fijar
  `metadata.mode` a «replay», MUST incluir en `metadata` la etiqueta explícita «REPRODUCCIÓN» y
  MUST incluir `replayed_at` en las propiedades de cada elemento.
- **FR-011**: En modo `replay` MUST NOT aplicarse la ventana de 24 horas por defecto, pero MUST
  aplicarse el resto de filtros y la paginación.
- **FR-012**: `last_ingestion` MUST ser siempre la última consulta correcta a USGS registrada,
  también en modo `replay`, donde MUST añadirse además el último `replayed_at`.
- **FR-013**: Una respuesta de reproducción MUST NOT mezclar datos de ambos esquemas, y los
  conteos del modo real MUST ser idénticos antes y después de una reproducción.
- **FR-014**: Los sintéticos de la reproducción MUST poder distinguirse y excluirse con un
  parámetro.

**Salud**

- **FR-015**: El endpoint de salud MUST informar del estado de la API y de la fecha de la última
  consulta correcta a USGS registrada (no de la última fila escrita), sin credenciales ni
  secretos.
- **FR-016**: Si la base falla, la salud MUST responder con estado degradado explícito y MUST
  NOT indicar normalidad.

**Estadísticas**

- **FR-017**: MUST ofrecer conteos por ventana fija de una hora UTC sobre el tiempo del evento
  (extremo final excluido, horas vacías con cero) y por país, incluyendo «Sin país asignado».
- **FR-018**: MUST ofrecer distribuciones de magnitud y de profundidad, contando aparte los
  registros sin valor.
- **FR-019**: MUST ofrecer comparación histórica con los mismos filtros (por ejemplo, últimas 24
  horas con magnitud ≥ 4 frente a la media diaria de 2025), con denominador que incluya los días
  sin eventos, «ND» si la media es cero y aviso de periodo reciente posiblemente incompleto.
- **FR-020**: Todo MUST calcularse desde el estado actual, sin contadores incrementales; una
  revisión MUST cambiar las agregaciones afectadas y una versión antigua tardía MUST NOT
  alterarlas.
- **FR-021**: Los filtros MUST ser exactamente los del mapa, y cada resultado MUST indicar
  periodo, filtros, unidad y registros sin valor.
- **FR-022**: Con selección truncada MUST NOT ofrecerse estadística global calculada sobre la
  muestra.
- **FR-023**: Toda respuesta de estadísticas en modo `replay` MUST identificarse como
  «REPRODUCCIÓN», MUST NOT mezclar esquemas y MUST permitir excluir los sintéticos.

**Errores y acceso**

- **FR-024**: Si la base falla, la API MUST responder con error HTTP explícito y cuerpo JSON, y
  MUST NOT devolver cero eventos como resultado válido.
- **FR-025**: Los parámetros inválidos MUST responder 422 con mensaje que indique el parámetro y
  el motivo.
- **FR-026**: El control de acceso entre orígenes MUST permitir solo el origen exacto del panel
  publicado (tomado de la configuración, sin secretos) y el origen local de desarrollo, solo los
  métodos de lectura y la comprobación previa, aceptar la cabecera de omisión de aviso del túnel
  y no usar cookies ni credenciales.
- **FR-027**: La API MUST escuchar en todas las interfaces dentro del contenedor y publicarse
  solo en la interfaz local del equipo; MUST NOT exponer rutas de administración ni de escritura
  y MUST NOT consultar a USGS.

**Heredado**

- **FR-028**: Se MUST comprobar qué alias y rutas heredados fuera del contrato usa el frontend
  entregado; los no usados MUST retirarse y los conservados MUST documentarse con motivo y
  fecha prevista de retirada.

**Calidad, rendimiento y evidencia**

- **FR-029**: Las consultas MUST usar los índices existentes, comprobado con el plan de
  ejecución; no se añaden índices ni cambios de modelo sin necesidad demostrada y justificada.
- **FR-030**: MUST medirse la latencia con al menos tres tamaños de resultado, indicando equipo y
  procedimiento (§10), y justificarse la agregación por ventanas.
- **FR-031**: Las pruebas MUST ser de comportamiento y la verificación MUST hacerse con el
  sistema real, con evidencia esperado/observado en `docs/evidence/006/` de cada caso de la
  historia 8.
- **FR-032**: El README MUST incluir ejemplos de consulta de cada endpoint y del modo
  `replay`, y `docs/report.md` un apartado con el contrato implementado, las decisiones y las
  desviaciones.

### Key Entities *(include if feature involves data)*

- **Evento (estado actual)**: versión vigente de un terremoto: identificador, tiempo de
  ocurrencia, magnitud, profundidad, coordenadas, país (puede faltar), marca de sintético y, en
  reproducción, `replayed_at`.
- **Colección de eventos**: respuesta con los puntos y sus `metadata`: generación, última
  ingesta, modo, etiqueta de reproducción, contadores (devueltos, total, magnitud nula, sin
  geometría) y paginación.
- **Estado de salud**: estado de la API y de la base, y última consulta correcta a USGS.
- **Resultado estadístico**: agregación con periodo, filtros, unidad, valores y registros sin
  valor.
- **Comparación histórica**: valor reciente frente a la media diaria de referencia, con ND y
  aviso de incompletitud.
- **Consulta a USGS registrada**: registro de cada extracción con su resultado; fuente de la
  última ingesta correcta.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de las respuestas de consulta de eventos tiene la misma estructura
  conforme al contrato, con y sin resultados, en ambos modos.
- **SC-002**: Tras cualquier reproducción, los conteos de la API en modo real son idénticos a los
  de antes (0 diferencias) y el 100 % de las respuestas de reproducción lleva la etiqueta
  «REPRODUCCIÓN».
- **SC-003**: En cada caso de la historia 8, el resultado observado coincide con el esperado (10
  de 10).
- **SC-004**: Con cualquier filtro, el total de las estadísticas coincide exactamente con el del
  mapa sin truncar (0 diferencias en la batería de pruebas).
- **SC-005**: Con la base caída, el 100 % de las peticiones de eventos y estadísticas recibe un
  error explícito y ninguna recibe «cero eventos» como válido; la salud indica degradado.
- **SC-006**: Recorrer todas las páginas de una selección truncada devuelve cada evento
  exactamente una vez.
- **SC-007**: Una persona ejecuta una consulta de cada endpoint y del modo reproducción
  siguiendo el README en menos de 5 minutos.
- **SC-008**: La consulta de la ventana por defecto y de un día completo de datos de 2025 responde
  en menos de 2 segundos en el equipo documentado, con al menos tres tamaños de resultado
  medidos.
- **SC-009**: Cada alias o ruta heredada fuera del contrato está retirada o documentada
  (100 %).

## Assumptions

- La API sigue siendo la de la spec 001, ajustada: no se reescribe sin motivo, y el contrato
  `CONTRATO-API.md` prevalece sobre ella.
- El modo se elige con un parámetro de consulta; no hay rutas separadas para la reproducción.
- La etiqueta «REPRODUCCIÓN» la emite la API; su presentación visual es de la spec 007.
- El máximo de puntos por respuesta se fija en el plan, se documenta y se puede cambiar por
  configuración; se elige para que el mapa siga fluido con los datos de 2025.
- Las estadísticas de una selección truncada se calculan sobre el total real en la base (no
  sobre la muestra) o se rechazan con aviso; la elección se fija en el plan.
- Sin cambios de modelo ni de índices de las specs 002 a 005 salvo necesidad demostrada y
  justificada.
- La salud toma la última ingesta correcta de las consultas registradas a USGS con resultado
  correcto.
- Fuera de alcance: panel Angular (spec 007), análisis y conclusiones (spec 008), despliegue en
  Netlify y túnel más allá de la configuración de acceso y el puerto, y costes.
- El código y los identificadores van en inglés; la documentación, la memoria y los textos
  visibles en español. Nada de datos en Git.
