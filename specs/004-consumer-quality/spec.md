# Feature Specification: Consumidor y calidad de los datos

**Feature Branch**: `004-consumer-quality`

**Created**: 2026-11-15

**Status**: Draft

**Input**: User description: "Spec 004: consumidor y calidad de los datos, sobre el modelo de la spec 002 y la ingesta de la spec 003. Objetivo: que el consumidor aplique reglas de validación y transformación explícitas, cumpliendo el principio III de la constitución (conservar, señalar o poner en cuarentena) y el IV (integración espacial verificable), cerrar la desviación heredada que envía a cuarentena la magnitud nula, y dejar en la memoria un análisis de calidad completo con acciones. Cubre las reglas del consumidor con código de motivo estable, el recuento de cada regla por SQL, el reprocesado de la cuarentena antigua, la integración espacial, los casos sintéticos separados y el análisis de calidad en seis dimensiones. Fuera de alcance: reproducción (005), contrato de la API (006) y panel (007). Sin cambios en el modelo salvo necesidad justificada; sin tocar la ingesta del productor."

**Depende de**: `specs/002-platform-data-model` (modelo y contrato de escritura) y
`specs/003-usgs-ingestion` (mensajes publicados y procedencia). Esta funcionalidad cierra la
desviación del principio III que las specs 002 y 003 dejaron abierta: el consumidor heredado
envía a cuarentena la magnitud nula y rechaza la negativa.

**Trazabilidad**: enunciado §4.3 (integración por punto en polígono, `ADM0_A3` único, «Sin país
asignado» no es error ni se atribuye al país más cercano, regla documentada para fronteras),
§6 (reglas explícitas; seis dimensiones; no rellenar nulos con cero; magnitud y profundidad
negativas no son errores por sí solas; cuarentena con motivo y original; casos dañados a
propósito separados; fechas en UTC con tiempo de ocurrencia separado del de procesamiento;
registrar qué transformaciones cambian los datos y cuántos registros afectan), §7 (upsert solo
si es más reciente; reprocesar no aumenta recuentos), §11 (pruebas «Magnitud nula»,
«Coordenadas inválidas», «Evento marítimo» y «Reiniciar consumidor»), §12 (apartado de calidad)
y §13 (criterio Calidad: «Completo + acciones»); FAQ 16, 17, 19 y 20; guía de entregables §2.4.
CONTRATO-API: la magnitud nula no cumple un filtro `min_mag` y debe contabilizarse. Constitución
v2.1.0: principios II, III, IV, VII y IX.

**Pruebas de aceptación del enunciado (§11) que esta funcionalidad sostiene**: «Magnitud nula»
(se conserva y se visualiza como ND), «Coordenadas inválidas» (cuarentena con motivo; ningún
punto inventado), «Evento marítimo» (sin país asignado; permanece en el análisis) y «Reiniciar
consumidor» (reanuda sin duplicar efectos ya persistidos). La visualización como ND corresponde
al panel (spec 007); aquí se garantiza que el valor llega nulo y contado.

## Clarifications

### Session 2026-11-16

- Q: ¿Qué debe hacer el consumidor cuando el modelo rechaza una versión que sus reglas aceptaron
  (por ejemplo, fecha fuera de la dimensión de fechas)? → A: Cuarentena con un motivo propio de
  rechazo por el modelo y el detalle del error de la base; el consumidor sigue con el siguiente
  mensaje. No se replican en el consumidor las restricciones del modelo.
- Q: ¿Dónde queda un evento recuperado al reprocesar la cuarentena y cómo se distingue el
  resultado del reprocesado? → A: En el espacio que indica el topic de la fila (real o
  reproducción); el reprocesado añade una nueva fila al registro de mensajes, identificada
  como reprocesado, sin sustituir la original; la fila de cuarentena guarda fecha y resultado.
- Q: ¿Cómo se identifica como sintético un evento que entra en el estado actual y en el
  historial? → A: Con la marca `synthetic` en `quality_flags` de estado actual y versión; la
  cuarentena usa su columna `is_synthetic`. Sin cambios en el modelo.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Conservar lo dudoso, rechazar solo lo intratable (Priority: P1)

Como responsable de datos, quiero que el consumidor guarde todo evento que pueda tratarse,
conservando los valores ausentes como ausentes y señalando las anomalías sin rechazarlas, y que
ponga en cuarentena únicamente lo que no puede interpretarse, con todos los motivos, para que
las estadísticas reflejen lo que dice la fuente y ningún dato se pierda ni se invente.

**Why this priority**: es el núcleo del principio III y de dos pruebas de aceptación del
enunciado; mientras no se cumpla, cada magnitud nula del feed desaparece del análisis.

**Independent Test**: enviar al sistema un conjunto etiquetado de mensajes (magnitud nula,
magnitud negativa, profundidad negativa, magnitud 10,5, evento antiguo, coordenadas fuera de
rango, geometría que no es un punto, sin identificador, JSON ilegible) y comprobar dónde acaba
cada uno y con qué motivo o señal.

**Acceptance Scenarios**:

1. **Given** un mensaje con `mag` nulo, **When** se procesa, **Then** el evento queda en el
   estado actual con magnitud nula, no cero, y aparece en el recuento de «magnitud ausente».
2. **Given** un mensaje con `magType` o profundidad nulos, **When** se procesa, **Then** se
   conservan nulos y el evento no va a cuarentena.
3. **Given** un mensaje con magnitud −0,5 o profundidad −2,7, **When** se procesa, **Then** se
   conservan tal cual y la profundidad negativa queda señalada con una marca de calidad
   estable; el evento sigue contando.
4. **Given** un mensaje con magnitud 10,5 o con una profundidad mayor que el radio terrestre,
   **When** se procesa, **Then** se conserva, queda señalado como valor fuera del rango
   plausible y no va a cuarentena.
5. **Given** un mensaje con latitud 145 o longitud −200, **When** se procesa, **Then** va a
   cuarentena con el motivo de coordenada fuera de rango, el original y la posición del
   mensaje; no se crea ningún punto.
6. **Given** un mensaje con geometría que no es un `Point`, o con coordenadas no numéricas,
   NaN o infinitas, **When** se procesa, **Then** va a cuarentena con el motivo
   correspondiente.
7. **Given** un mensaje sin `id`, sin `time` o sin `updated`, o con esos campos ilegibles,
   **When** se procesa, **Then** va a cuarentena y la cuarentena lista **todos** los motivos
   encontrados, no solo el primero.
8. **Given** un mensaje que no es JSON, **When** se procesa, **Then** va a cuarentena con el
   texto recibido y el motivo de JSON ilegible.
9. **Given** un mensaje del feed con un evento ocurrido hace más de 7 días, o con tiempo de
   ocurrencia en el futuro, **When** se procesa, **Then** no se rechaza por ello: se conserva
   y, si el tiempo es futuro, queda señalado.
10. **Given** un mensaje cuyo tipo no es terremoto, **When** llega al consumidor, **Then** se
    guarda como exclusión con su tipo y motivo y no entra en el estado actual.
11. **Given** cualquier mensaje tratable, **When** se guarda, **Then** el tiempo de ocurrencia,
    el de actualización en USGS y el de ingesta están en UTC y en columnas distintas, y el
    original queda íntegro.

---

### User Story 2 - Reprocesar lo que se rechazó por reglas retiradas (Priority: P1)

Como responsable de datos, quiero reprocesar con las reglas nuevas los mensajes que fueron a
cuarentena por reglas que esta funcionalidad retira, para recuperar esos eventos sin perder la
constancia de que un día se rechazaron.

**Why this priority**: sin esto, los eventos rechazados por la regla antigua (magnitud nula o
fuera de 0–10) seguirían fuera del análisis aunque la regla ya no exista.

**Independent Test**: con filas de cuarentena reales y sintéticas, ejecutar el reprocesado y
comprobar qué filas se recuperan, cuáles siguen en cuarentena y que ejecutarlo dos veces no
cambia nada.

**Acceptance Scenarios**:

1. **Given** una fila de cuarentena rechazada solo por magnitud nula o fuera de rango, **When**
   se reprocesa, **Then** el evento pasa al estado actual (si no existe ya una versión igual o
   más reciente), la fila de cuarentena queda marcada como reprocesada con fecha y resultado,
   y no se borra.
2. **Given** una fila rechazada por coordenadas inválidas, **When** se reprocesa, **Then** sigue
   en cuarentena, marcada como reprocesada con resultado «sigue rechazada» y los motivos
   vigentes.
3. **Given** el reprocesado ejecutado, **When** se ejecuta otra vez, **Then** ningún recuento
   cambia.
4. **Given** una fila sintética en cuarentena, **When** se reprocesa, **Then** se trata igual y
   el evento resultante, si lo hay, queda identificado como sintético.
5. **Given** la cuarentena reprocesada, **When** se consulta el registro de mensajes, **Then**
   se puede distinguir el resultado original del resultado del reprocesado.

---

### User Story 3 - País verificable para cada terremoto (Priority: P1)

Como responsable de la integración, quiero que cada terremoto reciba su país mediante una
operación geométrica reproducible sobre el catálogo entregado, con una regla fija para los
casos ambiguos y país nulo cuando no hay polígono, para que la integración sea verificable y no
dependa del texto descriptivo.

**Why this priority**: es la segunda fuente que convierte el proyecto en una integración; una
prueba de aceptación del enunciado depende de ella.

**Independent Test**: procesar puntos conocidos (interior de un país, océano abierto, un punto
sobre una frontera terrestre, un punto en un enclave) y comprobar el país asignado y que el
resultado es el mismo en ejecuciones repetidas.

**Acceptance Scenarios**:

1. **Given** un punto dentro de un polígono, **When** se procesa, **Then** recibe el
   identificador de esa entidad del catálogo, y nunca se deduce del campo `place`.
2. **Given** un punto en el océano, **When** se procesa, **Then** el país queda nulo, el evento
   permanece en el estado actual y cuenta en los totales; no se asigna el país más cercano.
3. **Given** un punto sobre una frontera o dentro de varias entidades, **When** se procesa,
   **Then** se aplica la regla documentada y el resultado es el mismo en cada ejecución.
4. **Given** el catálogo entregado, **When** arranca el consumidor, **Then** comprueba que el
   identificador de entidad es único y se detiene con un mensaje claro si no lo es.
5. **Given** el identificador asignado, **When** se consulta, **Then** existe en la dimensión de
   países y la integración se puede comprobar con una consulta.

---

### User Story 4 - Contar lo que hace cada regla (Priority: P2)

Como autora de la memoria, quiero saber cuántos registros afecta cada validación y cada
transformación, con el denominador explícito, a partir de lo almacenado, para documentar el
efecto de las decisiones sin contadores que se desvíen de la realidad.

**Why this priority**: el enunciado exige registrar qué transformaciones cambian los datos y
cuántos registros afectan; es el puente entre el consumidor y el análisis de calidad.

**Independent Test**: tras procesar un conjunto conocido, ejecutar las consultas documentadas y
comprobar que los recuentos coinciden con lo enviado.

**Acceptance Scenarios**:

1. **Given** los datos almacenados, **When** se ejecutan las consultas documentadas, **Then**
   se obtiene, por cada código de motivo de cuarentena y por cada marca de calidad, cuántos
   mensajes o eventos afecta, con el denominador (mensajes recibidos, versiones distintas o
   terremotos actuales).
2. **Given** un mensaje con varios motivos, **When** se cuenta, **Then** aparece en cada motivo
   pero cuenta una sola vez como mensaje rechazado.
3. **Given** los recuentos, **When** se comparan con el registro de mensajes, **Then**
   recibidos = nuevos + revisados + atrasados + repetidos + excluidos + rechazados.
4. **Given** casos sintéticos, **When** se cuenta, **Then** quedan fuera de los recuentos
   reales y se cuentan aparte.

---

### User Story 5 - Casos de prueba dañados a propósito, separados (Priority: P2)

Como responsable de la demostración, quiero inyectar mensajes dañados a propósito para probar
el consumidor con el sistema real, de modo que queden identificados como sintéticos y nunca se
mezclen con el análisis real.

**Why this priority**: necesario para evidenciar las pruebas de aceptación sin inventar errores
en los datos reales, como exige el enunciado.

**Independent Test**: inyectar el conjunto sintético, comprobar que cada caso acaba donde debe,
que todo lo que generó está marcado como sintético y que las consultas de análisis real no lo
incluyen.

**Acceptance Scenarios**:

1. **Given** un conjunto sintético documentado, **When** se inyecta en el sistema real,
   **Then** cada fila que genera (cuarentena, estado actual, versión, exclusión) queda
   identificada como sintética.
2. **Given** las consultas de calidad y de análisis, **When** se ejecutan, **Then** excluyen lo
   sintético por defecto y lo cuentan aparte.
3. **Given** el conjunto sintético, **When** se vuelve a inyectar, **Then** no aumenta ningún
   recuento.
4. **Given** un evento real, **When** se consulta, **Then** nunca aparece marcado como sintético.

---

### User Story 6 - Análisis de calidad completo con acciones (Priority: P2)

Como evaluadora, quiero un apartado de calidad en la memoria con consultas reproducibles,
resultados antes y después, acciones justificadas y limitaciones para las seis dimensiones del
enunciado, para valorar la calidad en el nivel sobresaliente.

**Why this priority**: es el criterio «Calidad» de la rúbrica; depende de que las reglas y los
recuentos existan.

**Independent Test**: repetir cada consulta del apartado contra la base y obtener los mismos
resultados que figuran en la memoria (salvo las cifras que crecen con el feed, que se anotan
con su fecha).

**Acceptance Scenarios**:

1. **Given** la memoria, **When** se lee el apartado de calidad, **Then** cada una de las seis
   dimensiones (completitud, unicidad, validez, consistencia, actualidad y exactitud) tiene al
   menos una comprobación con consulta, resultado, denominador, acción y limitación.
2. **Given** una comprobación con tratamiento, **When** se lee, **Then** muestra el resultado
   antes y después, sin sumar incidencias que pueden solaparse.
3. **Given** el apartado, **When** se busca la fuente, el periodo y el conjunto analizado,
   **Then** están indicados, y los casos sintéticos aparecen por separado.
4. **Given** la dimensión de exactitud, **When** se lee, **Then** explica qué se puede contrastar
   y qué no (comprobar rangos no demuestra la exactitud física).

### Edge Cases

- Magnitud que llega como texto numérico («4.2»): se convierte y se señala; como texto no
  numérico, se conserva nula y se señala.
- Profundidad ausente en las coordenadas (solo longitud y latitud): nula, sin cuarentena.
- Coordenadas con más de tres valores: se usan los tres primeros y se señala.
- Coordenada exactamente en el límite (longitud 180, latitud −90): válida.
- Tiempo de ocurrencia posterior al de actualización: se conserva y se señala como
  incoherente, no se rechaza.
- Tiempo de ocurrencia anterior al primer día de la dimensión de fecha (antes de 1900): el
  modelo lo rechaza; va a cuarentena con el motivo de rechazo por el modelo y el detalle del
  error, y el consumidor sigue con el siguiente mensaje (aclaración de la sesión 2026-11-16).
- Mensaje del topic de reproducción: mismas reglas, destino en el espacio de reproducción.
- Versión repetida de un evento que está en cuarentena por una regla vigente: se registra el
  mensaje como repetido o rechazado, sin crear otra fila de cuarentena.
- La misma versión llega primero a cuarentena (regla antigua) y después, tras el reprocesado,
  llega otra vez por el feed: no se duplica.
- Punto exactamente sobre un vértice compartido por tres entidades: la regla determinista
  elige una y la misma siempre.
- Catálogo geográfico con dos entidades de igual identificador: el consumidor no arranca.
- Marca de calidad nueva sobre un evento que ya existía sin ella: la revisión posterior
  sustituye el conjunto de marcas; una versión atrasada no las cambia.
- Reprocesar una fila cuyo evento ya tiene una versión más reciente en el estado actual: la
  versión reprocesada queda como atrasada en el historial y la fila se marca reprocesada.

## Requirements *(mandatory)*

### Functional Requirements

**Reglas de validación**

- **FR-001**: Toda regla de validación y transformación del consumidor MUST estar escrita en un
  catálogo documentado con su código estable, su dimensión de calidad, su efecto (cuarentena,
  exclusión, marca o transformación) y su justificación.
- **FR-002**: Un mensaje MUST ir a cuarentena únicamente si no puede tratarse: no es JSON; no es
  un objeto; le falta `id`, `time` o `updated`, o no son legibles; la geometría no es un `Point`;
  la longitud o la latitud faltan, no son numéricas, no son finitas o están fuera de
  [−180, 180] y [−90, 90]; o el modelo de datos rechaza la versión. En este último caso el motivo
  MUST ser un código propio de rechazo por el modelo con el detalle del error, y el consumidor
  MUST NOT replicar de antemano las restricciones del modelo ni reintentar el mensaje.
- **FR-003**: La cuarentena MUST conservar todos los motivos encontrados en el mensaje, el
  mensaje original (JSON o texto) y la posición del mensaje, una sola fila por mensaje.
- **FR-004**: La magnitud, el tipo de magnitud, la profundidad y el lugar ausentes MUST
  conservarse como nulos; MUST NOT sustituirse por cero ni por ningún valor inventado, y MUST
  poder contarse aparte.
- **FR-005**: La magnitud negativa y la profundidad negativa MUST conservarse; la profundidad
  negativa MUST señalarse con una marca estable. La magnitud negativa MUST NOT señalarse como
  anomalía: es un valor legítimo de las escalas locales.
- **FR-006**: Los valores fuera del rango plausible (magnitud mayor de 10 o menor de −2,
  profundidad mayor de 800 km) MUST conservarse y señalarse, no rechazarse.
- **FR-007**: El consumidor MUST NOT rechazar un evento por la antigüedad de su tiempo de
  ocurrencia ni por el topic del que procede; un tiempo de ocurrencia en el futuro (más de 5
  minutos después de la recepción) MUST conservarse y señalarse.
- **FR-008**: El consumidor MUST NOT rechazar un mensaje por haber visto antes su
  identificador: la repetición y la revisión las resuelve la regla de versiones del modelo.
- **FR-009**: Los mensajes cuyo tipo no sea terremoto MUST guardarse como exclusiones con su
  tipo, motivo y original, una vez por versión, y MUST NOT entrar en el estado actual ni en la
  cuarentena.
- **FR-010**: Las marcas de calidad MUST usar códigos estables documentados y MUST guardarse con
  el evento; una revisión posterior MUST sustituir el conjunto de marcas por el de la versión
  nueva.
- **FR-011**: Los tiempos de ocurrencia, actualización en USGS e ingesta MUST convertirse a UTC
  y guardarse por separado, conservando los valores originales en el original.
- **FR-012**: Las mismas reglas MUST aplicarse a los tres topics; solo cambia el espacio de
  destino.
- **FR-013**: Un mensaje defectuoso MUST NOT perderse ni bloquear la cola: termina en
  cuarentena con motivo y el consumidor continúa con el siguiente.

**Recuento**

- **FR-014**: Cuántos mensajes afecta cada código de motivo de cuarentena, cuántos eventos lleva
  cada marca de calidad y cuántos registros cambia cada transformación MUST poder obtenerse con
  consultas documentadas sobre lo almacenado, con el denominador explícito, sin contadores
  acumulados.
- **FR-015**: El registro de mensajes MUST permitir comprobar que recibidos = nuevos +
  revisados + atrasados + repetidos + excluidos + rechazados, contando solo las filas del tratamiento
  original; las filas de reprocesado se cuentan aparte.

**Reprocesado**

- **FR-016**: La entrega MUST ofrecer un procedimiento, ejecutable con una orden, que reprocese
  con las reglas vigentes las filas de cuarentena no reprocesadas, en el espacio al que
  pertenece cada una.
- **FR-017**: El reprocesado MUST ser idempotente, MUST NOT borrar filas de cuarentena, MUST
  marcar cada fila reprocesada con la fecha y el resultado (recuperada con su resultado de
  versión, o sigue rechazada con sus motivos vigentes). El reprocesado MUST escribir en el
  espacio que indica el topic de la fila (real o reproducción) y MUST añadir al registro de
  mensajes una fila nueva identificada como reprocesado, conservando la fila original con su
  resultado «rechazado»; repetir el reprocesado MUST NOT añadir más filas.
- **FR-018**: Un evento recuperado MUST pasar por la misma regla de versiones que un mensaje
  nuevo: no sustituye una versión más reciente ni duplica una existente.

**Integración espacial**

- **FR-019**: El país MUST obtenerse por punto en polígono sobre la copia entregada del
  catálogo, en WGS84, usando longitud y latitud; MUST NOT deducirse del texto del lugar.
- **FR-020**: El consumidor MUST comprobar al arrancar que el identificador de entidad del
  catálogo es único y MUST detenerse con un mensaje claro si no lo es.
- **FR-021**: Un punto sin polígono MUST quedar con país nulo y permanecer en el estado actual;
  MUST NOT atribuirse al país más cercano ni tratarse como error.
- **FR-022**: Para un punto sobre una frontera o contenido en varias entidades, la regla MUST
  estar documentada y ser determinista: la entidad de identificador menor en orden
  alfabético, y el evento MUST señalarse con una marca de ambigüedad.
- **FR-023**: La documentación MUST advertir de que los límites del catálogo están simplificados
  y de que la asignación no tiene precisión cartográfica.

**Casos sintéticos**

- **FR-024**: La entrega MUST incluir un conjunto sintético documentado que cubra cada regla
  del catálogo, y un procedimiento para inyectarlo en el sistema real.
- **FR-025**: Toda fila generada por un mensaje sintético (cuarentena, estado actual, versión,
  exclusión) MUST quedar identificada como sintética: en la cuarentena, con su columna
  `is_synthetic`; en el estado actual y en el historial, con la marca `synthetic` en las marcas
  de calidad. Las consultas de calidad y análisis MUST excluir ambas por defecto y contarlas
  aparte.
- **FR-026**: Inyectar el conjunto sintético varias veces MUST NOT aumentar ningún recuento.

**Análisis de calidad**

- **FR-027**: La memoria MUST incluir un apartado de calidad que indique fuente, periodo y
  conjunto analizado, y que para cada una de las seis dimensiones (completitud, unicidad,
  validez, consistencia, actualidad y exactitud) aporte al menos una comprobación con la
  consulta, el resultado, el denominador, la acción tomada y sus limitaciones.
- **FR-028**: Las comprobaciones con tratamiento MUST mostrar el resultado antes y después, y
  el apartado MUST NOT sumar incidencias que pueden solaparse.
- **FR-029**: La dimensión de actualidad MUST medir los retrasos entre ocurrencia,
  actualización en USGS e ingesta, aclarando que una revisión antigua aumenta la diferencia.
- **FR-030**: La dimensión de exactitud MUST explicar qué se puede contrastar y qué no.
- **FR-031**: Las consultas del apartado MUST ser reproducibles contra la base y MUST excluir
  los casos sintéticos.

**Límites y evidencia**

- **FR-032**: Esta funcionalidad MUST NOT cambiar la ingesta del productor, la reproducción, el
  contrato de la API ni el panel; MUST NOT modificar el modelo de las specs 002 y 003 salvo
  necesidad demostrada, justificada por escrito y reflejada en el diccionario de datos.
- **FR-033**: Cada historia MUST verificarse con el sistema real y dejar resultado esperado,
  observado y salida en la carpeta de evidencias; las pruebas de aceptación «Magnitud nula»,
  «Coordenadas inválidas», «Evento marítimo» y «Reiniciar consumidor» MUST quedar
  evidenciadas con casos sintéticos identificados.

### Key Entities *(include if feature involves data)*

Todas existen en el modelo de la spec 002; esta funcionalidad define cómo las usa el consumidor.

- **Evento actual y versión**: reciben los valores conservados (nulos incluidos), las marcas de
  calidad y el país; el original íntegro va en la versión.
- **Cuarentena**: una fila por mensaje intratable, con todos los motivos, el original, la
  posición del mensaje, si es sintético y, tras el reprocesado, cuándo y con qué resultado se
  reprocesó.
- **Exclusión**: versiones de elementos que no son terremotos, con tipo y motivo.
- **Registro de mensajes**: el resultado de cada mensaje; con el reprocesado, también el del
  segundo tratamiento, distinguible del primero.
- **Catálogo de reglas**: documento con cada código de motivo y de marca, su dimensión, efecto
  y justificación.
- **Conjunto sintético**: mensajes dañados a propósito, documentados caso a caso.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de los mensajes del conjunto sintético termina donde el catálogo de
  reglas indica, con el motivo o la marca esperados.
- **SC-002**: Un mensaje con magnitud nula, otro con magnitud negativa, otro con profundidad
  negativa y otro con un evento de más de 7 días quedan en el estado actual, y 0 de ellos en
  cuarentena.
- **SC-003**: Tras el reprocesado, el 100 % de las filas de cuarentena rechazadas solo por
  reglas retiradas pasa al estado actual o al historial, y ejecutarlo de nuevo cambia 0
  recuentos.
- **SC-004**: El 100 % de los terremotos actuales con país tiene un identificador que existe en
  la dimensión de países, y 0 países se han obtenido del texto del lugar.
- **SC-005**: Para 100 puntos repartidos por el mundo, dos ejecuciones de la asignación de país
  dan el mismo resultado en el 100 % de los casos.
- **SC-006**: Reiniciar el consumidor a mitad de un lote de 1.000 mensajes termina con los
  mismos recuentos que sin reinicio.
- **SC-007**: En el registro de mensajes, recibidos = nuevos + revisados + atrasados + repetidos
  + excluidos + rechazados, con diferencia 0.
- **SC-008**: El 0 % de las filas generadas por mensajes sintéticos aparece en las consultas de
  análisis real, y el 100 % está identificado como sintético.
- **SC-009**: Las seis dimensiones tienen al menos una comprobación con consulta, resultado,
  denominador, acción y limitación, y cada consulta repetida contra la base da el mismo
  resultado que la memoria en su fecha.
- **SC-010**: Un mensaje defectuoso no retrasa el siguiente más de un segundo ni detiene el
  consumidor.

## Assumptions

- Rango plausible: magnitud entre −2 y 10, profundidad hasta 800 km. Fuera de él el valor se
  conserva y se señala; nunca se rechaza. El límite de 800 km está por encima de la
  profundidad máxima registrada en la fuente (unos 700 km).
- Marca de tiempo futuro: más de 5 minutos después de la recepción, para absorber desajustes de
  reloj.
- Regla para fronteras: la entidad de identificador menor en orden alfabético, con marca de
  ambigüedad. Con la escala del catálogo (1:110.000.000) los límites están simplificados; se
  documenta que la asignación no tiene precisión cartográfica.
- El reprocesado de la cuarentena se lanza a mano con una orden, como la carga histórica; no se
  ejecuta solo.
- La identificación de lo sintético se apoya en la columna `is_synthetic` de la cuarentena que
  ya existe y en la marca `synthetic` de `quality_flags` para eventos y versiones (confirmado el
  2026-11-16); no se añaden columnas al modelo. Una exclusión sintética se reconoce por la
  extracción o el mensaje que la originó, que la memoria documenta.
- Las filas de cuarentena reales existentes al implementar (2 por `magnitude_out_of_range`) son
  el primer caso real del reprocesado.
- La ND en el panel y el tratamiento de la magnitud nula en los filtros de la API corresponden
  a las specs 006 y 007; aquí se garantiza el dato y su recuento.
- Idioma: código, códigos de motivo y marcas en inglés; documentación en español.
- La rama parte de `003-usgs-ingestion`, que aún no está en `main`.
