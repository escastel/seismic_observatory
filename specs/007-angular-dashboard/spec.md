# Feature Specification: Panel Angular conforme al enunciado

**Feature Branch**: `007-angular-dashboard`

**Created**: 2026-11-16

**Status**: Draft

**Input**: User description: "Spec 007: panel Angular conforme al enunciado, que consulta solo la API de la 006 (datos reales y de reproducción) y se publica en Netlify, sobre la plataforma (002), la ingesta (003), el consumidor (004), la reproducción (005) y la API de consulta (006). Objetivo: que el panel cumpla enunciado §8 (puntos 1 a 7), §9 (consulta cada 60 s, túnel y Netlify) y §11 (cerrar y reabrir el túnel, reproducción «REPRODUCCIÓN», nulos como ND, evento marítimo), FAQ 25 a 32, y los principios VI, VII y VIII de la constitución. Se parte del frontend entregado (`frontend/`), que se revisa y se adapta, no se reescribe sin motivo."

**Depende de**: `specs/006-query-api` (contrato HTTP en `specs/006-query-api/contracts/api.md`, fuente
de verdad), `specs/005-historical-replay` (datos de reproducción), `specs/004-consumer-quality`
(nulos, cuarentena, sintéticos), `specs/003-usgs-ingestion` (`last_ingestion`) y
`specs/002-platform-data-model`. La 006 ya está integrada en `main`.

**Trazabilidad**: constitución principios VI, VII y VIII, enunciado §8 (puntos 1 a 7), §9 y §11,
FAQ 25 a 32.

**Divergencias detectadas en el panel actual** (punto de partida, no requisitos): lee el formato
antiguo de las estadísticas y con la API de la 006 deja de pintar; filtra el país por nombre y no
por identificador; la tabla se queda en los 100 primeros eventos e ignora el total y la
paginación; los filtros de fecha se interpretan en hora local; no hay modo reproducción, ni
etiqueta «REPRODUCCIÓN», ni aviso de datos desactualizados, ni distinción entre error de
parámetros, base no disponible y «sin datos»; pide a la API parámetros heredados que esta ignora.

**Pruebas de aceptación del enunciado (§11) que sostiene**: «cerrar y reabrir el túnel»,
«Reproducción histórica» (parte del panel), nulos mostrados como ND, evento marítimo bajo «Sin
país asignado» y evento nuevo visible en mapa y tabla.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver los eventos recientes en mapa y tabla con la API real (Priority: P1)

Como persona que consulta el observatorio, quiero abrir el panel y ver en el mapa y en una tabla
los terremotos de las últimas 24 horas, con su magnitud, profundidad, hora UTC y país, para saber
qué ha ocurrido y con qué datos se ha construido lo que veo.

**Why this priority**: sin esto el panel no muestra nada utilizable; hoy no carga correctamente con
la API de la 006. Es el mínimo viable de la defensa.

**Independent Test**: con el sistema levantado y eventos cargados, abrir el panel y comprobar que
el mapa y la tabla muestran los mismos eventos que devuelve la API con los mismos filtros.

**Acceptance Scenarios**:

1. **Given** eventos reales de las últimas 24 h, **When** se abre el panel, **Then** el mapa dibuja
   un círculo por evento (tamaño por magnitud, color por profundidad, con leyenda) y la tabla
   lista los mismos eventos.
2. **Given** un evento con magnitud nula o profundidad nula, **When** se muestra en mapa, ficha o
   tabla, **Then** aparece como «ND» (mismo criterio para ambos campos) y no se oculta ni se
   representa como cero.
3. **Given** un evento marítimo sin país asignado, **When** se abre su ficha o su fila, **Then**
   figura bajo «Sin país asignado».
4. **Given** un evento nuevo ingerido tras la carga, **When** transcurre el siguiente refresco,
   **Then** aparece en mapa y tabla sin recargar la página y sin duplicar los anteriores.
5. **Given** un evento con coordenadas no válidas, **When** llega en la respuesta, **Then** se omite
   del mapa y el panel informa de cuántos se han omitido.
6. **Given** una ficha de evento, **When** se abre, **Then** muestra id, magnitud, profundidad, hora
   UTC, país, continente y subregión como texto, de modo que un texto con marcas no se interpreta.

---

### User Story 2 - Conocer la frescura de los datos y el estado del backend (Priority: P1)

Como persona que defiende el sistema, quiero ver cuándo leyó el panel por última vez, cuándo generó
la API su respuesta y cuándo consultó por última vez a USGS, y recibir un aviso claro si los datos
están desactualizados o el backend no responde, para no confundir un dato viejo con la actualidad.

**Why this priority**: es el principio VIII y la prueba «cerrar y reabrir el túnel»; un panel que
muestra datos viejos sin avisar engaña.

**Independent Test**: con el panel abierto, detener el túnel o la API, comprobar el aviso y la
última lectura conservada y rotulada; reabrir y comprobar la recuperación automática.

**Acceptance Scenarios**:

1. **Given** una lectura correcta, **When** se muestra el estado, **Then** aparecen tres instantes
   distintos y rotulados (última lectura correcta del panel, generación de la respuesta y última
   ingesta) y el periodo consultado.
2. **Given** que `last_ingestion` supera el umbral configurable de antigüedad, **When** se muestra
   el estado, **Then** aparece un aviso de datos desactualizados con la antigüedad.
3. **Given** que el backend deja de responder (túnel cerrado, base caída o tiempo agotado a los
   15 s), **When** falla un refresco, **Then** el panel avisa, conserva los eventos y gráficos de
   la última lectura correcta, los identifica como tal con su hora, y no los presenta como
   actuales.
4. **Given** el backend caído, **When** se reabre el túnel, **Then** el siguiente refresco (60 s)
   recupera los datos y retira el aviso sin intervención ni recarga.
5. **Given** distintas situaciones, **When** ocurren, **Then** el panel muestra mensajes
   diferentes para parámetros inválidos (422), base no disponible (503), sistema degradado en la
   salud y «sin eventos» válido (cero resultados no es un error).
6. **Given** una petición aún en curso, **When** llega el momento del siguiente refresco, **Then**
   no se lanza otra solapada.

---

### User Story 3 - Filtrar y que mapa, tabla y gráficos coincidan (Priority: P1)

Como persona que analiza, quiero filtrar por fecha, magnitud mínima y país y que mapa, tabla y
gráficos apliquen exactamente el mismo filtro, para poder contrastar las cifras entre vistas.

**Why this priority**: es el principio VII y §8.5; filtros incoherentes invalidan cualquier
conclusión.

**Independent Test**: aplicar un filtro y comprobar que el total de la tabla, los eventos del mapa
y el total de los gráficos coinciden; repetir con otro filtro.

**Acceptance Scenarios**:

1. **Given** un filtro aplicado, **When** se actualiza el panel, **Then** mapa, tabla y gráficos se
   alimentan de la misma petición de filtros y sus totales coinciden.
2. **Given** fechas de inicio y fin, **When** se introducen, **Then** se interpretan en UTC, se
   indica la zona en el propio campo y el inicio es inclusivo y el fin exclusivo.
3. **Given** el selector de país, **When** se elige un país, **Then** se filtra por su
   identificador y no por su nombre; las opciones salen de un catálogo de países.
4. **Given** «Sin país asignado», **When** se consulta el filtro de país, **Then** no se ofrece como
   opción filtrable (la API no puede filtrar por identificador nulo) y el panel lo explica, pero
   sí se muestra en la ficha y en el análisis por país.
5. **Given** un filtro inválido (inicio posterior al fin, magnitud no numérica), **When** se aplica,
   **Then** el panel lo detecta o muestra el error 422 de forma comprensible, sin vaciar la vista.

---

### User Story 4 - Entender el análisis: ventanas horarias, países, distribuciones y comparación (Priority: P2)

Como persona que analiza, quiero ver los conteos por hora UTC y por país, las distribuciones de
magnitud y profundidad y la comparación de las últimas 24 horas con la media diaria de 2025, cada
cifra con su periodo, filtros, unidad y registros sin valor, para sostener conclusiones sin
confundirlas con una predicción.

**Why this priority**: es §8.2 a §8.4; depende de que la visualización base (P1) funcione.

**Independent Test**: con un conjunto conocido, comparar cada gráfico con las cifras de la API de
estadísticas con los mismos filtros.

**Acceptance Scenarios**:

1. **Given** una respuesta de estadísticas, **When** se pintan los gráficos, **Then** se muestran los
   conteos por ventana de una hora UTC (con las horas vacías a cero) y por país, incluido «Sin país
   asignado».
2. **Given** distribuciones de magnitud y profundidad, **When** se muestran, **Then** los registros
   sin valor se indican aparte («ND») y no se suman a ningún tramo.
3. **Given** la comparación histórica, **When** se muestra, **Then** presenta las últimas 24 h frente
   a la media diaria de 2025 con los mismos filtros, muestra «ND» si la media es cero y advierte de
   que el periodo reciente puede estar incompleto.
4. **Given** cualquier resultado analítico, **When** se muestra, **Then** indica periodo, filtros
   aplicados, unidad y registros sin valor, y no se presenta como predicción ni riesgo.
5. **Given** que el mapa está truncado, **When** se muestran estadísticas, **Then** el panel avisa del
   truncado y las estadísticas siguen siendo las del conjunto completo, sin recalcular nada en el
   cliente sobre la muestra.
6. **Given** un periodo de más de 10.000 horas, **When** la API responde 422, **Then** el panel
   explica el límite y sugiere acotar el periodo.
7. **Given** una persona que no distingue colores, **When** consulta los gráficos, **Then** cada
   valor es legible por texto, etiqueta o tabla equivalente y no solo por color.

---

### User Story 5 - Revisar la reproducción histórica sin mezclarla con lo real (Priority: P1)

Como persona que defiende el sistema, quiero cambiar a la vista de reproducción histórica y ver
todo identificado como «REPRODUCCIÓN», para demostrar la reproducción sin que se confunda con la
actualidad.

**Why this priority**: es el principio VI y la prueba «Reproducción histórica»; mezclar invalida
las conclusiones.

**Independent Test**: anotar los totales en modo real, cambiar a reproducción, comprobar etiqueta y
datos, volver y comprobar que los totales reales no cambian.

**Acceptance Scenarios**:

1. **Given** el selector de modo, **When** se elige reproducción, **Then** mapa, tabla, gráficos y
   estado muestran la etiqueta «REPRODUCCIÓN» tomada de la respuesta de la API.
2. **Given** el cambio de modo, **When** se produce, **Then** se limpian las capas del mapa, la
   tabla y los gráficos anteriores y nunca coexisten eventos de ambos modos en la vista.
3. **Given** el modo reproducción, **When** se consulta, **Then** se muestra la última reproducción
   (`last_replayed_at`), se puede excluir los sintéticos y el periodo se aplica sin la ventana de
   24 h que la API usa en modo real.
4. **Given** el regreso al modo real, **When** se consulta, **Then** los totales reales coinciden con
   los anteriores a la reproducción.
5. **Given** una respuesta en modo reproducción sin etiqueta, **When** llega, **Then** el panel no la
   muestra como real y avisa.

---

### User Story 6 - Navegar todo el conjunto con una tabla accesible (Priority: P2)

Como persona que usa teclado o lector de pantalla, quiero una tabla con todos los campos y la
posibilidad de recorrer todos los resultados, para consultar los datos sin depender del mapa ni
del color.

**Why this priority**: es §8.7 y accesibilidad; no bloquea la defensa básica.

**Independent Test**: consultar un periodo con más eventos que el límite por página y comprobar que
se pueden recorrer todos; usar el panel solo con teclado.

**Acceptance Scenarios**:

1. **Given** más eventos que el máximo por respuesta, **When** se consulta la tabla, **Then** se
   muestra cuántos se muestran frente al total y se puede continuar hasta recorrer todos.
2. **Given** el mapa truncado, **When** se muestra, **Then** el aviso de truncado es visible y
   explica cuántos eventos faltan.
3. **Given** la tabla, **When** se recorre, **Then** magnitud y profundidad figuran en texto
   (incluido «ND») y los campos son los mismos que en la ficha del mapa.
4. **Given** solo teclado, **When** se usa el panel, **Then** filtros, selector de modo, tabla y
   controles son operables y el foco es visible; los cambios de estado se anuncian en una región
   `aria-live`.
5. **Given** el uso de color, **When** se codifica profundidad o aviso, **Then** hay además texto,
   forma o patrón que transmite lo mismo.

---

### User Story 7 - Publicar el panel en Netlify tras un túnel y defenderlo (Priority: P2)

Como persona que presenta el proyecto, quiero un procedimiento documentado para levantar el túnel,
construir el panel contra su URL y publicarlo en Netlify, y comprobarlo desde otro dispositivo,
para la defensa.

**Why this priority**: es §9; la publicación efectiva la hace la persona autora, la spec entrega el
procedimiento y su comprobación.

**Independent Test**: seguir el procedimiento del README en un equipo limpio hasta tener el panel
funcionando en local con la API; la publicación se valida con la persona autora.

**Acceptance Scenarios**:

1. **Given** el procedimiento, **When** se sigue, **Then** cubre levantar el túnel, fijar la URL
   HTTPS en la configuración del panel antes de compilar, instalar con versiones fijadas, arrancar,
   publicar y comprobar desde otro dispositivo.
2. **Given** la configuración y el repositorio, **When** se revisan, **Then** no contienen
   `authtoken` ni secretos, y el origen de Netlify y el de desarrollo figuran como los únicos
   orígenes autorizados por CORS.
3. **Given** el modo `demo` del panel actual, **When** se resuelve, **Then** queda retirado o
   etiquetado de forma inequívoca como sintético y nunca puede confundirse con datos reales.

---

### User Story 8 - Evidencia verificable (Priority: P3)

Como evaluadora, quiero ver el resultado esperado y observado de cada comprobación en navegador
real, con capturas de los filtros usados, para dar cada prueba por superada.

**Why this priority**: constitución IX; sin evidencia no hay aceptación.

**Independent Test**: revisar `docs/evidence/007/` y repetir una comprobación a partir de sus
instrucciones.

**Acceptance Scenarios**:

1. **Given** el panel y la API levantados, **When** se ejecutan los escenarios (evento nuevo,
   nulo como ND, evento marítimo, truncado, filtros coherentes, cerrar y reabrir el túnel,
   reproducción aislada), **Then** cada uno deja esperado, observado y captura con los filtros.
2. **Given** la lógica pura del panel (adaptación de respuestas, formato, estados), **When** se
   ejecutan sus pruebas, **Then** comprueban comportamiento y no el texto del código.
3. **Given** el informe y el README, **When** se revisan, **Then** contienen el apartado de esta
   spec y el procedimiento de la defensa.

---

### Edge Cases

- Respuesta con cero eventos válida: «sin eventos» con el periodo y filtros, sin error.
- Respuesta de `/api/salud` con estado `degraded`: aviso propio, distinto de «backend inaccesible».
- Cambio de filtros o de modo mientras hay una petición en curso: la respuesta antigua no debe
  pintarse sobre la nueva vista.
- Respuesta de modo distinto al solicitado: no se muestra.
- Campos nulos o ausentes en una feature (magnitud, profundidad, país, continente, subregión): se
  muestra ND o «Sin país asignado», nunca `undefined`, `NaN` ni vacío ambiguo.
- Coordenadas fuera de rango o no numéricas: se omiten del mapa y se cuentan; siguen en la tabla.
- Texto de `place` con marcas HTML o caracteres especiales: se muestra literal.
- Más de 1000 eventos: truncado visible; las estadísticas son del conjunto completo.
- Periodo muy largo (más de 10.000 horas): 422 explicado.
- Reloj del navegador desajustado: la antigüedad de los datos se calcula frente a `generated` de la
  respuesta, no solo frente al reloj local.
- Túnel de ngrok con página intermedia: el panel envía la cabecera acordada para evitarla y, si
  recibe HTML en lugar de JSON, lo trata como backend inaccesible.
- Cambio de la URL del túnel: exige reconstruir el panel; se documenta.
- Sin conexión del navegador: se trata como backend inaccesible.

## Requirements *(mandatory)*

### Functional Requirements

**Consumo de la API**

- **FR-001**: El panel MUST consultar únicamente `GET /api/eventos`, `GET /api/estadisticas` y
  `GET /api/salud` de la API de la 006 y MUST NOT consultar USGS ni otro origen de datos.
- **FR-002**: El panel MUST adaptar las respuestas al contrato de la 006 (`metadata`, `by_country`,
  `hourly`, `comparison`, distribuciones con elementos y sin valor, `country_id`, `country_name`) y
  MUST NOT depender del formato antiguo ni enviar parámetros que la API ignora.
- **FR-003**: La configuración (modo, URL base de la API, periodo de refresco, cabecera de
  salto de aviso, umbral de antigüedad) MUST estar en un fichero público de configuración sin
  secretos.
- **FR-004**: Una respuesta con forma inesperada MUST tratarse como error comprensible y MUST NOT
  provocar un fallo de la interfaz.

**Mapa**

- **FR-005**: El mapa MUST mostrar fondo, fronteras de países y un círculo por evento con tamaño
  por magnitud y color por profundidad, con leyenda de ambos, y los nulos MUST mostrarse como ND con
  el mismo criterio para magnitud y profundidad.
- **FR-006**: La ficha de un evento MUST mostrar id, magnitud, profundidad, hora UTC, país (o «Sin
  país asignado»), continente y subregión como texto, nunca como HTML.
- **FR-007**: El mapa MUST mantener una sola capa de eventos que se sustituye completa en cada
  refresco, sin acumulación ni duplicados.
- **FR-008**: Los eventos con coordenadas no válidas MUST omitirse del mapa y contarse de forma
  visible.

**Tabla**

- **FR-009**: La tabla MUST ofrecer todos los campos del evento con magnitud y profundidad en texto
  y MUST recorrer la paginación de la API hasta cubrir el conjunto filtrado, mostrando cuántos
  eventos se muestran frente al total.
- **FR-010**: Cuando la respuesta esté truncada, el panel MUST mostrarlo de forma visible para el
  mapa y la tabla.

**Filtros**

- **FR-011**: El panel MUST ofrecer filtros de fecha (con zona UTC explícita, inicio inclusivo y fin
  exclusivo), magnitud mínima y país por identificador, tomado de un catálogo de países.
- **FR-012**: Mapa, tabla y gráficos MUST alimentarse de la misma petición de filtros y sus totales
  MUST coincidir.
- **FR-013**: «Sin país asignado» MUST NOT ofrecerse como filtro por identificador; el panel MUST
  explicarlo y mostrarlo en la ficha y en el análisis por país.
- **FR-014**: Los filtros inválidos MUST validarse en el cliente cuando sea posible y los errores
  422 MUST mostrarse con el parámetro afectado, conservando la última vista válida.

**Análisis**

- **FR-015**: El panel MUST mostrar conteos por ventana de una hora UTC y por país (incluido «Sin
  país asignado»), distribuciones de magnitud y profundidad con los registros sin valor aparte, y
  la comparación de las últimas 24 h con la media diaria de 2025 con los mismos filtros.
- **FR-016**: La comparación MUST mostrar «ND» si la media diaria es cero y MUST advertir de que el
  periodo reciente puede estar incompleto.
- **FR-017**: Todo resultado analítico MUST indicar periodo, filtros aplicados, unidad y registros
  sin valor, y MUST NOT presentarse como predicción ni evaluación de riesgo.
- **FR-018**: Con el mapa truncado, las estadísticas MUST seguir siendo las del conjunto completo y
  el panel MUST NOT recalcularlas en el cliente a partir de la muestra.
- **FR-019**: El error por periodo demasiado largo MUST explicarse al usuario.
- **FR-020**: Los gráficos MUST ser legibles sin depender solo del color; si se añade una
  biblioteca de gráficos MUST quedar fijada a una versión exacta y justificada.

**Estado del sistema**

- **FR-021**: El panel MUST mostrar, diferenciados y rotulados, la última lectura correcta del
  panel, el instante de generación de la respuesta (`generated`), la última ingesta
  (`last_ingestion`) y el periodo consultado.
- **FR-022**: El panel MUST avisar cuando la última ingesta supere un umbral de antigüedad
  configurable.
- **FR-023**: Si el backend no responde (error de red, tiempo de 15 s agotado, respuesta no JSON o
  5xx), el panel MUST avisar, conservar la última lectura correcta e identificarla como tal con su
  hora.
- **FR-024**: El panel MUST refrescar cada 60 s (configurable), sin lanzar una petición mientras
  otra siga en curso, y MUST recuperarse solo en el siguiente refresco al volver el backend.
- **FR-025**: El panel MUST distinguir y explicar de forma distinta: parámetros inválidos (422),
  base no disponible (503), estado `degraded` en la salud, backend inaccesible y «sin eventos».
- **FR-026**: Una respuesta tardía de una consulta anterior (por cambio de filtros o de modo) MUST
  descartarse.

**Reproducción**

- **FR-027**: El panel MUST ofrecer un selector de modo real/reproducción y MUST mostrar «REPRODUCCIÓN»,
  tomada de la respuesta de la API, en mapa, tabla, gráficos y estado.
- **FR-028**: Al cambiar de modo, el panel MUST limpiar capas, tabla y gráficos anteriores y MUST NOT
  mostrar nunca en una misma vista datos reales y de reproducción.
- **FR-029**: En reproducción, el panel MUST mostrar la última reproducción, permitir excluir datos
  sintéticos y aplicar el periodo elegido sin la ventana de 24 h propia del modo real.
- **FR-030**: Una respuesta de reproducción sin etiqueta, o de un modo distinto al pedido, MUST NOT
  mostrarse como válida.

**Accesibilidad y presentación**

- **FR-031**: Todos los textos del panel MUST estar en español, con contraste suficiente, controles
  operables con teclado y foco visible.
- **FR-032**: Los avisos y cambios de estado MUST anunciarse mediante regiones `aria-live`.
- **FR-033**: La información MUST NOT depender solo del color.

**Despliegue**

- **FR-034**: El repositorio MUST incluir la configuración de publicación en Netlify de la SPA y la
  configuración del panel con la URL HTTPS del túnel fijada antes de compilar; el backend MUST
  permanecer local y fuera de Netlify.
- **FR-035**: La documentación MUST describir levantar el túnel, instalar con versiones fijadas,
  arrancar, publicar, autorizar el origen exacto de Netlify en CORS junto al de desarrollo y
  comprobar desde otro dispositivo.
- **FR-036**: Ni el repositorio ni el código del panel MUST contener `authtoken` ni secretos.
- **FR-037**: El modo `demo` MUST retirarse del panel, o conservarse solo etiquetado como sintético
  de forma inequívoca y sin posibilidad de mezclarse con datos reales.

**Calidad y evidencia**

- **FR-038**: La lógica pura (adaptación de respuestas, formato de nulos y fechas, cálculo de
  estados y de filtros) MUST tener pruebas de comportamiento.
- **FR-039**: Cada escenario de aceptación MUST comprobarse en navegador real con la API levantada y
  dejar esperado, observado y captura con los filtros en `docs/evidence/007/`.
- **FR-040**: El informe y el README MUST incluir el apartado de esta spec y el procedimiento de la
  defensa; las versiones de Angular, ngx-leaflet y Leaflet MUST permanecer fijadas.
- **FR-041**: No se versionarán datos descargados, capturas con datos sensibles ni ficheros de
  configuración con secretos.

### Key Entities

- **Evento mostrado**: terremoto con id, magnitud (puede ser nula), profundidad (puede ser nula),
  hora UTC, país (o ninguno), continente, subregión y, en reproducción, `replayed_at` y marca de
  sintético.
- **Filtro de consulta**: periodo UTC, magnitud mínima, país por identificador, modo y exclusión de
  sintéticos; una única instancia alimenta mapa, tabla y gráficos.
- **Lectura del panel**: respuesta correcta más reciente con su hora de lectura, `generated`,
  `last_ingestion`, periodo, modo y etiqueta.
- **Estado del panel**: situación derivada (normal, desactualizado, degradado, backend inaccesible,
  error de parámetros, sin eventos).
- **Resultado analítico**: conteos por hora y país, distribuciones, comparación, con periodo,
  filtros, unidad y registros sin valor.
- **Catálogo de países**: identificador y nombre de los países filtrables.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Con el sistema levantado, el panel muestra mapa y tabla con datos en menos de 5
  segundos desde la apertura y sus totales coinciden en el 100 % de los filtros probados.
- **SC-002**: Un evento nuevo ingerido aparece en mapa y tabla en el siguiente refresco (como
  máximo 60 s más la duración de la petición), sin duplicados.
- **SC-003**: Con los filtros de la batería de pruebas, los totales de mapa, tabla y gráficos
  coinciden en el 100 % de los casos.
- **SC-004**: Con el backend inaccesible, el aviso aparece como máximo 15 s tras el siguiente
  refresco fallido, la última lectura permanece visible y rotulada, y tras reabrirlo el panel se
  recupera en un solo refresco sin recargar.
- **SC-005**: El 100 % de los valores nulos de magnitud y profundidad se muestran como ND y el 100 %
  de los eventos sin país figuran como «Sin país asignado» en mapa, tabla y análisis.
- **SC-006**: En modo reproducción, el 100 % de las vistas lleva la etiqueta «REPRODUCCIÓN» y, tras
  volver al modo real, los totales reales son idénticos a los anteriores.
- **SC-007**: Con más eventos que el máximo por respuesta, se pueden recorrer todos desde la tabla y
  el truncado es visible; las estadísticas coinciden con el total de la API.
- **SC-008**: Todo el panel es operable solo con teclado y los avisos de estado llegan a un lector de
  pantalla; ninguna información depende únicamente del color.
- **SC-009**: Una persona sigue el procedimiento del README y deja el panel funcionando contra la API
  en menos de 15 minutos.
- **SC-010**: Los 7 escenarios de aceptación listados en la historia 8 tienen evidencia esperado y
  observado antes de darse por superados.

## Assumptions

- La API de la 006 es el contrato; si falta algo en ella se documenta como cambio justificado en
  lugar de resolverse en el cliente.
- El catálogo de países para el filtro se obtiene de los datos ya disponibles para el panel (las
  fronteras publicadas o los países de las estadísticas) sin añadir un servicio nuevo; si no
  bastara, se documentará la necesidad como cambio de la API.
- «Sin país asignado» no es filtrable por la limitación del contrato; es una decisión de
  presentación, no un error.
- El modo `demo` se retira por defecto, porque los datos sintéticos no deben poder confundirse con los
  reales (principio VI); solo se conserva si el plan demuestra que sigue siendo necesario y queda
  etiquetado.
- Umbral de desactualización por defecto: de varios periodos de ingesta (el valor concreto se fija en
  el plan) y configurable.
- El periodo de refresco es de 60 s y el tiempo máximo de petición de 15 s, ambos de §9 y configurables.
- Angular, ngx-leaflet y Leaflet permanecen en las versiones fijadas; no se añaden dependencias salvo
  que una biblioteca resuelva un requisito y quede fijada.
- La publicación en Netlify y el túnel ngrok los ejecuta la persona autora; esta spec entrega la
  configuración, el procedimiento y su comprobación local.
- Las conclusiones redactadas y el análisis narrativo quedan para la spec 008; el panel solo muestra
  las cifras que las sostienen.
- Se trabaja en equipos Windows y Linux; los pasos documentados valen en ambos.
