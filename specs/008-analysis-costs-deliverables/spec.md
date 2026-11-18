# Feature Specification: Análisis, rendimiento, costes y cierre de entregables

**Feature Branch**: `008-analysis-costs-deliverables`

**Created**: 2026-11-17

**Status**: Draft

**Input**: User description: "Spec 008: análisis con conclusiones, complejidad y rendimiento, costes y cierre de entregables, sobre la plataforma (002), la ingesta (003), el consumidor (004), la reproducción (005), la API de consulta (006) y el panel (007). Objetivo: que el proyecto cumpla enunciado §8 (conclusiones fundamentadas), §10 (complejidad, mediciones, costes) y §12 (entregables), y los principios VII y IX de la constitución. No añade funcionalidad al panel ni a la API: produce análisis, mediciones, informe de costes y trazabilidad final de entregables."

**Depende de**: `specs/002-platform-data-model` a `specs/007-angular-dashboard`. La 007 todavía no
está integrada en `main` (comprobado al crear la rama), de modo que esta rama parte de
`007-angular-dashboard`.

**Trazabilidad**: constitución principios VII y IX; enunciado §8, §10, §11, §12 y §13.

**Estado heredado** (punto de partida, no requisitos): el panel (007) muestra periodo, filtros,
unidad y registros sin valor, y la API (006) calcula las estadísticas. Existen `docs/calidad.md`,
`docs/evaluacion-financiera.md` (VAN a cinco años con flujos que parecen supuestos sin
justificar), `docs/evidence/002/index-benchmark.md` (índices con 1.000.000 de filas sintéticas en
un esquema aparte) y `tests/benchmark/api_latency.py` (la 006 midió con 34.045 eventos y dejó
pendiente medir con 1.000.000).

**Trampa de equivalencia conocida**: el catálogo de 2025 cargado solo contiene magnitud ≥ 4 (unos
18.300 eventos), mientras el feed en vivo incluye todas las magnitudes. Comparar «últimas 24 h
sin filtro» con la media diaria de 2025 no es equivalente (el panel mostró razón 3,87 así). La
comparación válida aplica los mismos filtros (por ejemplo magnitud ≥ 4) a ambos periodos.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Conclusiones fundamentadas sobre datos reales (Priority: P1)

La evaluadora lee el apartado de análisis de la memoria y encuentra al menos tres conclusiones
sobre los datos reales. Cada una indica cifras, filtros exactos, periodo, unidad, registros sin
valor y una captura del panel con esos mismos filtros, y se puede regenerar con una consulta o
llamada a la API que figura junto a la cifra.

**Why this priority**: es lo que el enunciado §8 evalúa como «conclusiones» y lo que distingue el
proyecto de una colección de gráficos (principio VII). Sin esto el resto es infraestructura.

**Independent Test**: tomar cada conclusión, ejecutar su consulta o llamada documentada sobre el
sistema levantado y comprobar que la cifra coincide con la publicada, dentro de la tolerancia que
el propio texto declara para datos en vivo, y que la captura muestra los mismos filtros.

**Acceptance Scenarios**:

1. **Given** el sistema con el catálogo de 2025 y el feed en vivo, **When** se ejecuta la
   consulta de una conclusión, **Then** devuelve la cifra publicada (o una cifra cuya diferencia
   se explica por el instante de ejecución, que consta en el texto) con el mismo periodo, filtros
   y unidad.
2. **Given** una conclusión que compara las últimas 24 h con la media diaria de 2025, **When** se
   revisan sus filtros, **Then** ambos periodos usan los mismos filtros de magnitud, tipo y
   ámbito, y el denominador histórico incluye los días con cero eventos.
3. **Given** cualquier conclusión, **When** se lee, **Then** declara los registros sin valor
   excluidos, advierte de que el periodo reciente puede estar incompleto y de que la cobertura de
   detección y los tipos de magnitud varían, y no presenta nada como predicción ni como
   evaluación de riesgo.
4. **Given** datos de reproducción o sintéticos en la base, **When** se calculan las cifras del
   análisis real, **Then** quedan excluidos; si se usa reproducción, aparece en un apartado
   aparte etiquetado «REPRODUCCIÓN».

---

### User Story 2 - Complejidad y rendimiento medidos (Priority: P1)

La evaluadora encuentra una justificación de coste medio y peor caso para al menos tres
operaciones (búsqueda de versiones por identificador, integración geográfica, agregación por
ventanas) y mediciones de tiempo y memoria con al menos tres tamaños de entrada, equipo y
procedimiento, incluyendo la comparación entre búsqueda secuencial, diccionario y consulta sin y
con índice, y el razonamiento sobre 100 millones de registros.

**Why this priority**: §10 y el principio IX lo exigen; la medición de 1.000.000 de filas de la
API quedó pendiente y es el hueco concreto más visible.

**Independent Test**: repetir el procedimiento documentado en el mismo equipo y comprobar que los
resultados son del mismo orden de magnitud que los publicados; comprobar que cada tabla separa
medidas de supuestos.

**Acceptance Scenarios**:

1. **Given** el procedimiento documentado, **When** se ejecuta con tres o más tamaños de entrada,
   **Then** se registran tiempo y memoria por tamaño y operación, con equipo y versión de cada
   componente.
2. **Given** la medición de índices de la 002, **When** se redacta el apartado, **Then** se
   reutiliza por referencia y no se vuelve a medir lo ya medido.
3. **Given** la prueba de latencia de la API con 34.045 eventos, **When** se completa con
   1.000.000 de filas sintéticas, **Then** los datos de escala quedan marcados como sintéticos,
   aislados del análisis real y eliminados o aislados al terminar.
4. **Given** una extrapolación a 100 millones de registros, **When** se presenta, **Then** consta
   como supuesto razonado, nunca como medida.

---

### User Story 3 - Costes honestos con supuestos explícitos (Priority: P2)

La evaluadora encuentra un informe de costes que cubre hardware, electricidad, almacenamiento,
transferencia, mantenimiento y tiempo de desarrollo, con cada supuesto explícito y los valores
medidos separados de los supuestos. Las cuotas gratuitas indican sus límites y qué ocurre al
superarlos, y hay una propuesta de escalado y mejoras.

**Why this priority**: obligatorio por §10 y por el principio IX, pero depende de las medidas de
la historia 2 para ser sólido.

**Independent Test**: para cada cifra del informe, comprobar que es una medida con enlace a
evidencia o un supuesto con su valor y fuente, y que no hay ningún beneficio económico sin
definición medible.

**Acceptance Scenarios**:

1. **Given** `docs/evaluacion-financiera.md`, **When** se revisa frente al principio IX, **Then**
   cada flujo queda justificado con supuestos trazables o se retira, y no queda ningún beneficio
   inventado.
2. **Given** el plan gratuito de Netlify y de ngrok, **When** se describen, **Then** se indican
   sus límites y la consecuencia de superarlos, sin tratarlos como coste cero.
3. **Given** que el observatorio no tiene un beneficio económico definido, **When** se trata el
   ROI, **Then** solo se calcula si se define un beneficio medible y justificable; en caso
   contrario se declara que no se estima y por qué.

---

### User Story 4 - Trazabilidad y cierre de entregables (Priority: P2)

La evaluadora (y la persona autora antes de entregar) dispone de una matriz que enlaza cada una de las
11 pruebas de aceptación de §11 con su spec y su evidencia en `docs/evidence/002` a `007`, cada
entregable de §12 con su fichero y cada criterio de §13 con su sección de la memoria. Los huecos
quedan señalados con lo que falta por demostrar.

**Why this priority**: evita entregar con pruebas sin evidencia o enlaces rotos; es el cierre
de todo el proyecto.

**Independent Test**: recorrer la matriz y abrir cada enlace; cada prueba, entregable y criterio
debe tener destino existente o un hueco explícito con su procedimiento.

**Acceptance Scenarios**:

1. **Given** las 11 pruebas de §11, **When** se revisa la matriz, **Then** cada una indica spec,
   evidencia observada y estado (superada con evidencia, parcial o pendiente), sin marcar como
   superada ninguna sin evidencia ejecutada.
2. **Given** `docs/report.md`, **When** se revisan índice, enlaces y cifras repetidas, **Then**
   los enlaces resuelven y las cifras coinciden entre secciones.
3. **Given** el repositorio, **When** se revisa su higiene, **Then** no hay en Git `node_modules`,
   credenciales, volúmenes ni datos descargados, y los hallazgos se corrigen o se documentan.
4. **Given** las pruebas pendientes en el equipo Linux (specs 002, 003, 005 y 006) y la
   comprobación del panel desde otro dispositivo físico, **When** se cierra, **Then** cada una
   figura como hueco con procedimiento para que la persona autora lo ejecute, no como superada.

---

### User Story 5 - Guion de apoyo para la explicación individual (Priority: P3)

La persona autora dispone de un guion que recorre el flujo completo (USGS, Kafka, consumidor,
PostgreSQL, API, panel) con los puntos que conviene poder explicar, las decisiones de diseño y
dónde está la evidencia de cada una.

**Why this priority**: ayuda, pero la explicación y la decisión técnica propia las redacta y
defiende la persona autora; no es evaluable por sí mismo.

**Independent Test**: seguir el guion con el sistema levantado y comprobar que cada paso remite a
un fichero o evidencia existente.

**Acceptance Scenarios**:

1. **Given** el guion, **When** se sigue paso a paso, **Then** cada etapa del flujo tiene su
   descripción breve, su evidencia y las preguntas previsibles, sin texto redactado como
   decisión propia de la persona autora.

---

### Edge Cases

- Los datos en vivo cambian entre la ejecución de una consulta y su lectura: cada cifra lleva el
  instante de ejecución y se indica la tolerancia esperada.
- Una media histórica de cero para el filtro elegido: se muestra ND, no una razón infinita ni cero.
- Un día del periodo histórico sin eventos: cuenta en el denominador.
- El filtro de magnitud excluye registros sin magnitud: se contabilizan aparte, no como cero.
- Mezcla de tipos de magnitud en una distribución: se separa o se advierte.
- La medición con 1.000.000 de filas agota memoria o disco del equipo: se documenta el límite
  alcanzado y se mide con el tamaño máximo que lo permite.
- La medición se ejecuta con el esquema real accesible: los datos sintéticos no deben entrar en
  ninguna cifra del análisis real.
- Una prueba de §11 depende de un hecho que solo puede comprobarse en Linux u otro dispositivo:
  consta como hueco con procedimiento.
- Un enlace de `docs/report.md` apunta a un fichero movido o purgado.
- Un fichero de datos o credenciales ya versionado en la historia: se informa y no se reescribe
  la historia sin confirmación explícita.

## Requirements *(mandatory)*

### Functional Requirements

**Análisis (§8, principio VII)**

- **FR-001**: La memoria MUST contener al menos tres conclusiones sobre datos reales, elegidas a
  la vista de los datos, cada una con cifras, filtros exactos, periodo, unidad, registros sin
  valor y captura del panel con los mismos filtros.
- **FR-002**: Las cifras MUST salir de la API de consulta o de consultas SQL sobre la tabla de
  estado actual, nunca de recálculos sobre la muestra del mapa ni del cliente.
- **FR-003**: Toda comparación entre periodos MUST usar los mismos filtros en ambos, incluir en
  el denominador los días sin eventos y mostrar ND cuando la media sea cero.
- **FR-004**: Cada conclusión MUST advertir de que el periodo reciente puede estar incompleto y de
  que la cobertura de detección y los tipos de magnitud varían, y MUST NOT presentarse como
  predicción de terremotos ni evaluación de riesgo.
- **FR-005**: Cada cifra MUST ir acompañada de la consulta o llamada que la regenera y del
  instante de ejecución.
- **FR-006**: Los datos sintéticos y de reproducción MUST quedar fuera del análisis real; un
  análisis de reproducción, si existe, MUST ir en un apartado aparte etiquetado «REPRODUCCIÓN».
- **FR-007**: La memoria MUST explicar la trampa de equivalencia del catálogo ≥ 4 frente al feed
  completo y mostrar la comparación corregida frente a la que dio razón 3,87.

**Complejidad y rendimiento (§10, principio IX)**

- **FR-008**: La memoria MUST justificar, con coste medio y peor caso, al menos la búsqueda de
  versiones por identificador, la integración geográfica y la agregación por ventanas.
- **FR-009**: Las mediciones de tiempo y memoria MUST cubrir al menos tres tamaños de entrada e
  indicar equipo, versiones y procedimiento repetible.
- **FR-010**: MUST compararse búsqueda secuencial, diccionario y consulta sin y con índice, y
  razonarse el comportamiento con 100 millones de registros como supuesto declarado.
- **FR-011**: MUST reutilizarse por referencia la medición de índices de la 002 y completarse la
  medición de latencia de la API con 1.000.000 de filas sintéticas, sin repetir lo ya medido.
- **FR-012**: Los datos de escala MUST estar marcados como sintéticos, aislados del esquema real y
  eliminados o aislados tras la medición.
- **FR-013**: Cada tabla o figura de rendimiento y costes MUST distinguir entre valores medidos y
  supuestos.

**Costes (§10, principio IX)**

- **FR-014**: El informe de costes MUST cubrir hardware, electricidad, almacenamiento,
  transferencia, mantenimiento y tiempo de desarrollo, con cada supuesto explícito y su fuente o
  razón.
- **FR-015**: Las cuotas gratuitas (Netlify, ngrok) MUST describir sus límites y la consecuencia
  de superarlos, sin contarlas como coste cero.
- **FR-016**: `docs/evaluacion-financiera.md` MUST revisarse frente al principio IX: cada flujo
  justificado con supuestos trazables o retirado.
- **FR-017**: El ROI MUST estimarse solo si se define un beneficio medible y justificable; si no,
  se declara que no se estima. MUST NOT inventarse ningún beneficio económico.
- **FR-018**: La memoria MUST incluir una propuesta de escalado y mejoras coherente con el stack
  permitido y con las mediciones.

**Cierre de entregables (§11, §12, §13)**

- **FR-019**: MUST existir una matriz que enlace cada una de las 11 pruebas de §11 con su spec y
  su evidencia en `docs/evidence/002` a `007`, con estado y hueco por demostrar; ninguna prueba
  se marca superada sin evidencia ejecutada de resultado esperado y observado.
- **FR-020**: MUST existir una matriz de cada entregable de §12 contra su fichero y de cada
  criterio de §13 contra su sección de la memoria.
- **FR-021**: `docs/report.md` MUST tener índice completo, enlaces que resuelven y cifras
  consistentes entre secciones.
- **FR-022**: MUST revisarse la higiene del repositorio (sin `node_modules`, credenciales,
  volúmenes ni datos descargados en Git) y registrar el resultado; cualquier corrección que
  implique reescribir historia requiere confirmación explícita.
- **FR-023**: Las pruebas pendientes en Linux (specs 002, 003, 005 y 006) y la comprobación del
  panel desde otro dispositivo MUST figurar como huecos con procedimiento ejecutable por la
  persona autora.
- **FR-024**: MUST entregarse un guion de apoyo del flujo completo que no sustituya la
  explicación ni la decisión técnica propias de la persona autora.

**Restricciones transversales**

- **FR-025**: El contrato de la API (006) y el panel (007) MUST NOT modificarse; un cambio solo se
  admite si se demuestra necesario y se documenta como cambio justificado.
- **FR-026**: Toda medición MUST ejecutarse con el sistema real y guardar resultado esperado y
  observado en `docs/evidence/008/`.
- **FR-027**: El código de medición nuevo MUST ser mínimo, en inglés, y sus pruebas MUST comprobar
  comportamiento; la documentación MUST estar en español; no se versionan datos ni secretos.

### Key Entities

- **Conclusión**: afirmación sobre los datos reales con cifras, filtros, periodo, unidad,
  registros sin valor, captura, consulta de regeneración e instante de ejecución.
- **Medición**: resultado de tiempo y memoria para una operación, un tamaño de entrada y un
  equipo, con procedimiento; marcada como medida.
- **Supuesto**: valor o extrapolación no medidos, con su valor, fuente o razón.
- **Partida de coste**: concepto (hardware, electricidad, almacenamiento, transferencia,
  mantenimiento, desarrollo) con importe, tipo (medido o supuesto) y supuestos asociados.
- **Entrada de trazabilidad**: prueba de §11, entregable de §12 o criterio de §13, con destino
  (spec, evidencia, fichero o sección), estado y hueco.
- **Hueco**: comprobación pendiente con quién la ejecuta, procedimiento y evidencia esperada.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Existen al menos 3 conclusiones y el 100 % de sus cifras se regeneran con la
  consulta o llamada documentada, coincidiendo con lo publicado o con la diferencia explicada por
  el instante de ejecución.
- **SC-002**: El 100 % de las comparaciones entre periodos usa filtros idénticos en ambos y
  documenta el tratamiento de días sin eventos y de media cero; la comparación corregida sustituye
  a la de razón 3,87 en la memoria.
- **SC-003**: Hay mediciones de tiempo y memoria con al menos 3 tamaños de entrada para el 100 %
  de las operaciones justificadas, y la medición de la API con 1.000.000 de filas está completada
  o su imposibilidad documentada con el tamaño máximo alcanzado.
- **SC-004**: El 100 % de las cifras de rendimiento y coste está etiquetado como medida o
  supuesto, y 0 beneficios económicos carecen de definición medible.
- **SC-005**: Las 11 pruebas de §11, todos los entregables de §12 y todos los criterios de §13
  tienen entrada en la matriz, con 0 enlaces rotos y 0 pruebas superadas sin evidencia.
- **SC-006**: La revisión de higiene encuentra 0 ficheros de datos descargados, credenciales,
  `node_modules` o volúmenes versionados, o cada hallazgo está resuelto o documentado.
- **SC-007**: Cada hueco que depende de la persona autora tiene un procedimiento que puede ejecutarse en
  menos de 30 minutos y una ruta de evidencia asignada.
- **SC-008**: Una persona que no conoce el proyecto puede localizar la evidencia de cualquier
  prueba de aceptación en menos de 2 minutos desde la matriz.

## Assumptions

- La explicación individual y la decisión técnica propia las redacta y defiende la persona autora; el
  guion solo organiza el material.
- Las conclusiones se eligen con los datos reales a la vista; los temas candidatos (reparto por
  país o subregión incluido «Sin país asignado», últimas 24 h frente a media diaria de 2025 con
  los mismos filtros, profundidad o magnitud por región, patrón por ventana horaria UTC) no se
  prescriben.
- El análisis vive en `docs/report.md` con consultas reproducibles, sin notebook ni informes
  automáticos, como `docs/calidad.md`.
- Los equipos de medición son el Windows 11 de la persona autora y, cuando esté disponible, el Linux;
  las medidas de un equipo no se extrapolan a otro sin decirlo.
- La medición con 1.000.000 de filas usa el esquema sintético aislado de la 002; si el equipo no
  lo soporta, se mide el máximo alcanzable y se documenta.
- Los precios de hardware, electricidad y servicios son supuestos con fecha y fuente, no medidas.
- No hay beneficio económico definido para el observatorio, por lo que el ROI por defecto es «no
  se estima»; solo cambia si la persona autora define un beneficio medible.
- Fuera de alcance: nuevas funciones del panel o de la API, contratar servicios cloud, generación
  automática de informes y la explicación oral.
- Dependencias externas de la persona autora: pruebas en Linux de las specs 002, 003, 005 y 006 y la
  comprobación del panel desde otro dispositivo físico; la spec deja procedimiento y hueco.
- Orquestación según `CLAUDE.md`: la sesión principal hace mediciones, cifras y conclusiones;
  agentes Haiku, tablas y redacción mecánica a partir de la evidencia; nunca dos ejecuciones de
  `tests/db` a la vez.
