# Feature Specification: Ingesta desde USGS

**Feature Branch**: `003-usgs-ingestion`

**Created**: 2026-11-15

**Status**: Draft

**Input**: User description: "Spec 003: ingesta desde USGS (feed en vivo, carga histórica y recuperación de huecos), sobre el modelo de datos de la spec 002. Objetivo: que el productor registre cada consulta a USGS y conserve los originales antes de transformar nada, como exige el principio V de la constitución, y que el histórico obligatorio quede cargado en el espacio real. Cubre el feed en vivo (registro de cada consulta, original guardado una vez por huella, purga, exclusiones conservadas, reintentos ante 429 y 5xx, nada se borra, estado de publicación tras la confirmación), la carga histórica de 2025 mundial con magnitud ≥ 4 (subdivisión sin truncar, deduplicación, ficheros fuera de Git, reanudable y comprobable), la recuperación de huecos tras paradas largas y `last_ingestion` como última consulta correcta al feed. Fuera de alcance: reglas de validación del consumidor (004), reproducción acelerada (005), contrato de la API (006) y panel."

**Depende de**: `specs/002-platform-data-model` (modelo, plataforma y contratos). Esta
funcionalidad cierra la desviación del principio V que la 002 dejó abierta: el productor no
registraba las extracciones, no guardaba el original y no purgaba.

**Trazabilidad**: enunciado §4.1 (datos recientes: consulta cada 60 segundos, campos, filtro
por tipo conservando el motivo de exclusión, documentación de la respuesta), §4.2 (histórico:
2025 mundial con magnitud ≥ 4, división en meses, subdivisión sin truncar, deduplicación entre
intervalos, registro de consultas, descargar una vez y reutilizar), §5 puntos 1 a 6 (original y
metadatos antes de transformar, retención, comparación con el estado persistente, clave y
contenido del mensaje, confirmación antes de marcar, fallos de la fuente) y su párrafo final (no
borrar lo que sale de la ventana; explicar cómo recuperar un hueco de más de 24 horas), §12
(registro de consultas y procedencia; nada de grandes descargas en Git) y §13 (criterio de
extracción: carga con análisis de tipos); FAQ 8, 10, 15, 21 y 31; guía de entregables §2.3;
CONTRATO-API («`last_ingestion`: última consulta correcta a USGS»). Constitución v2.1.0:
principios I, II, III, V y IX.

**Pruebas de aceptación del enunciado (§11) que esta funcionalidad sostiene**: «Recibir un
evento nuevo» (US1: la versión nueva se publica una vez y llega al espacio real), «Reenviar la
misma versión» (US1 y US2: una versión ya publicada no se vuelve a publicar, y repetir la carga
no aumenta ningún recuento) y «Recibir una versión posterior» (US1: la revisión se publica). La
parte de esas pruebas que corresponde al almacenamiento quedó evidenciada en la spec 002; la de
«Recibir después una versión antigua» corresponde al consumidor y al modelo, y aquí solo se
garantiza que la ingesta no publica como novedad una versión atrasada.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Feed en vivo con procedencia completa (Priority: P1)

Como autora de la memoria, quiero que cada consulta al feed de las últimas 24 horas quede
registrada, que su contenido original se conserve antes de transformarlo y que cada elemento
recibido tenga un destino conocido (publicado, ya conocido o excluido), para poder reconstruir
qué datos entraron en el sistema y de dónde proceden.

**Why this priority**: es la obligación central del principio V y la única vía por la que entran
datos nuevos; sin ella no hay evidencia de extracción ni puede calcularse la última ingesta.

**Independent Test**: dejar el sistema funcionando una hora y comprobar que hay un registro por
cada consulta, que los contenidos idénticos se han guardado una sola vez, que la suma de
terremotos y excluidos coincide con los elementos recibidos en cada consulta y que los
terremotos nuevos han llegado al espacio real.

**Acceptance Scenarios**:

1. **Given** el sistema arrancado, **When** transcurre un ciclo de consulta, **Then** existe un
   registro de esa consulta con su destino, su duración, sus intentos, su resultado y el momento
   en que la fuente generó la respuesta.
2. **Given** una consulta correcta con N elementos, **When** se procesa, **Then** el registro
   indica cuántos se recibieron, cuántos eran terremotos, cuántos se excluyeron y cuántas
   versiones nuevas se publicaron, y recibidos = terremotos + excluidos.
3. **Given** dos consultas seguidas cuyos eventos son idénticos aunque cambie la cabecera de la
   respuesta, **When** se registran, **Then** constan dos consultas y un único original
   almacenado, con la fecha de última observación actualizada.
4. **Given** una respuesta que contiene un elemento que no es un terremoto (por ejemplo, una
   voladura), **When** se procesa, **Then** el elemento no se publica, queda guardado con su
   tipo, su motivo de exclusión y la consulta en que se vio, y no se repite si vuelve a aparecer
   la misma versión.
5. **Given** una versión de un evento ya publicada, **When** vuelve a aparecer en consultas
   posteriores, **Then** no se publica de nuevo.
6. **Given** una versión nueva, **When** el broker no confirma su recepción, **Then** no se
   marca como publicada y se vuelve a intentar en el ciclo siguiente.
7. **Given** un evento que estaba en la ventana de 24 horas, **When** deja de aparecer en el
   feed, **Then** sigue almacenado con todas sus versiones.
8. **Given** consultas correctas y fallidas intercaladas, **When** se pregunta por la última
   ingesta, **Then** se obtiene el momento de la última consulta correcta al feed, haya traído
   novedades o no.

---

### User Story 2 - Histórico obligatorio de 2025 cargado y comprobable (Priority: P1)

Como evaluador, quiero que el histórico mundial de 2025 con magnitud igual o superior a 4 y tipo
terremoto esté cargado en el espacio real mediante un procedimiento documentado, repetible y
con recuentos comprobables, para verificar que la extracción es completa y no se ha truncado.

**Why this priority**: es el conjunto de datos obligatorio del enunciado y la base de la
comparación histórica del análisis; una carga incompleta invalida las conclusiones.

**Independent Test**: ejecutar el procedimiento de carga sobre una base sin histórico y comparar
el número de terremotos de 2025 almacenados con el total que la fuente declara para el mismo
filtro; repetir el procedimiento y comprobar que no cambia ningún recuento.

**Acceptance Scenarios**:

1. **Given** una base sin histórico, **When** se ejecuta la carga de 2025, **Then** el número de
   terremotos de 2025 con magnitud ≥ 4 almacenados en el espacio real coincide con el total que
   declara la fuente para ese filtro en el momento de la extracción.
2. **Given** el año dividido en meses y un mes cuyo número de eventos supera el máximo que la
   fuente entrega en una respuesta, **When** se consulta, **Then** ese mes se subdivide hasta
   que cada parte cabe completa, y ninguna respuesta se acepta truncada.
3. **Given** un evento que aparece en dos intervalos contiguos, **When** termina la carga,
   **Then** existe una sola vez.
4. **Given** la carga terminada, **When** se revisa el registro, **Then** cada petición consta
   con sus parámetros, su intervalo, su resultado y su número de registros, y la suma por
   intervalos menos las repeticiones coincide con el total.
5. **Given** la carga interrumpida a mitad (corte de red o parada), **When** se vuelve a
   ejecutar, **Then** continúa sin repetir los intervalos ya completados y termina con el mismo
   resultado que una carga sin interrupciones.
6. **Given** la carga completada, **When** se ejecuta otra vez, **Then** no se crea ningún
   evento ni versión que ya existiera.
7. **Given** los ficheros descargados, **When** se revisa el repositorio y la base, **Then** los
   ficheros están en la ubicación de datos fuera del control de versiones y la base conserva de
   cada uno su huella y su ruta, de modo que se puede comprobar que el fichero no ha cambiado.
8. **Given** un evento del histórico, **When** se consulta, **Then** consta que procede del
   catálogo histórico y no del feed, y está en el espacio real, no en el de reproducción.

---

### User Story 3 - La ingesta resiste los fallos de la fuente (Priority: P2)

Como responsable de la operación, quiero que un fallo de USGS (saturación, error del servidor,
tiempo agotado o respuesta ilegible) quede registrado, se reintente con prudencia y no altere lo
ya almacenado, para que la ingesta se recupere sola y los fallos sean visibles.

**Why this priority**: la fuente es externa y falla; sin esto un fallo pasa desapercibido o
deja el sistema parado, pero el recorrido normal (historias 1 y 2) puede demostrarse antes.

**Independent Test**: sustituir la fuente por una simulada que devuelva saturación con tiempo de
espera indicado, error de servidor, tiempo agotado y contenido ilegible, y comprobar el registro
de cada caso, las esperas aplicadas y que el ciclo siguiente funciona con normalidad.

**Acceptance Scenarios**:

1. **Given** que la fuente responde que hay demasiadas peticiones e indica cuánto esperar,
   **When** se reintenta, **Then** la espera aplicada no es inferior a la indicada.
2. **Given** un error temporal del servidor, **When** se reintenta y la fuente responde bien,
   **Then** consta una sola consulta correcta con el número de intentos realizados.
3. **Given** que se agotan los reintentos, **When** termina el ciclo, **Then** consta la consulta
   con su tipo de fallo y su detalle, no se publica nada, no se borra nada y el ciclo siguiente
   vuelve a intentarlo.
4. **Given** una respuesta que no es JSON o que no tiene la estructura esperada, **When** se
   recibe, **Then** se registra como tal, se conserva lo recibido para su diagnóstico y no se
   publica ningún elemento de esa respuesta.
5. **Given** fallos durante varios ciclos, **When** se pregunta por la última ingesta, **Then**
   sigue siendo la de la última consulta correcta y no avanza.
6. **Given** un elemento sin identificador o con una fecha de actualización ilegible dentro de
   una respuesta por lo demás válida, **When** se procesa, **Then** el resto de elementos se
   trata con normalidad y el defectuoso no se pierde en silencio: queda contabilizado y
   localizable en el original conservado.

---

### User Story 4 - Recuperación de huecos tras una parada larga (Priority: P2)

Como responsable de datos, quiero que, si la ingesta ha estado parada más tiempo del que cubre
el feed de 24 horas, el sistema me avise del periodo perdido y me indique la orden exacta para
recuperarlo desde el catálogo histórico, para que la serie del espacio real no tenga huecos que
parezcan días sin terremotos.

**Why this priority**: sin esto una parada de un fin de semana deja un vacío falso en el
análisis. El enunciado pide explicar cómo se recupera el hueco; aquí además se puede ejecutar y
demostrar, reutilizando el procedimiento de carga del catálogo sin añadir automatismos.

**Independent Test**: registrar una última consulta correcta de hace 36 horas, arrancar la
ingesta, comprobar que avisa del hueco con la orden de recuperación, ejecutar esa orden y
verificar que los eventos del periodo quedan almacenados y que ninguno está duplicado.

**Acceptance Scenarios**:

1. **Given** una última consulta correcta al feed de hace más de 24 horas, **When** arranca la
   ingesta, **Then** avisa de forma visible del periodo no cubierto (desde esa consulta hasta el
   inicio de la ventana actual del feed) y muestra la orden exacta para recuperarlo; el feed en
   vivo empieza a consultarse con normalidad.
2. **Given** una última consulta correcta de hace menos de 24 horas, o un sistema recién
   instalado sin consultas previas, **When** arranca la ingesta, **Then** no hay aviso: no hay
   hueco.
3. **Given** el aviso de un hueco, **When** se ejecuta la orden indicada, **Then** los eventos
   de todas las magnitudes ocurridos en ese periodo quedan en el espacio real y las consultas
   constan con el propósito de recuperación de huecos.
4. **Given** eventos del periodo recuperado que también llegaron por el feed, **When** termina
   la recuperación, **Then** cada evento existe una sola vez.
5. **Given** una recuperación interrumpida, **When** se vuelve a ejecutar la misma orden,
   **Then** termina con el mismo resultado que si no se hubiera interrumpido.

---

### User Story 5 - Los originales no crecen sin límite (Priority: P3)

Como responsable de la operación, quiero que los originales del feed se eliminen pasada la
retención definida, conservando para siempre el registro de las consultas, para que el
almacenamiento no crezca sin control.

**Why this priority**: es necesario a medio plazo, pero una semana de funcionamiento cabe sin
purga y no condiciona las demás historias.

**Independent Test**: introducir originales con fecha de última observación anterior a la
retención y otros recientes, dejar pasar un ciclo de purga y comprobar cuáles permanecen.

**Acceptance Scenarios**:

1. **Given** originales del feed no observados desde hace más días que la retención, **When**
   se ejecuta la purga periódica, **Then** se eliminan y queda constancia de cuántos.
2. **Given** originales observados dentro de la retención, **When** se ejecuta la purga,
   **Then** se conservan.
3. **Given** las referencias a los ficheros del catálogo histórico, **When** se ejecuta la
   purga, **Then** no se eliminan, tengan la antigüedad que tengan.
4. **Given** una consulta cuyo original se ha purgado, **When** se consulta el registro,
   **Then** la consulta sigue constando con su huella y sus recuentos.

---

### User Story 6 - Ampliar el histórico con 2026 (Priority: P3)

Como responsable del panel, quiero poder cargar también los terremotos de 2026 anteriores a la
puesta en marcha del feed, con el mismo procedimiento y el mismo filtro que 2025, para que el
panel muestre el año en curso y no solo el histórico obligatorio y las últimas horas.

**Why this priority**: enriquece el panel, pero el enunciado no lo exige y la comparación
histórica obligatoria se hace contra 2025; no debe retrasar las demás historias.

**Independent Test**: ejecutar el procedimiento de carga para el periodo del 1 de enero de 2026
hasta hoy con magnitud ≥ 4 y comprobar que el recuento almacenado coincide con el declarado por
la fuente y que los recuentos de 2025 no cambian.

**Acceptance Scenarios**:

1. **Given** el histórico de 2025 cargado, **When** se ejecuta la carga para 2026 hasta la
   fecha actual con el mismo filtro, **Then** los terremotos de ese periodo quedan en el espacio
   real, con el catálogo como procedencia, y el total coincide con el declarado por la fuente.
2. **Given** la carga de 2026 terminada, **When** se cuentan los eventos de 2025, **Then** el
   recuento es el mismo que antes.
3. **Given** eventos recientes de 2026 que también están en el feed, **When** termina la carga,
   **Then** cada evento existe una sola vez y conserva su versión más reciente.
4. **Given** ambas cargas, **When** se revisa el registro, **Then** cada una consta con su
   periodo, su filtro y su fecha de extracción, de modo que la memoria puede indicar qué
   periodos tienen todas las magnitudes y cuáles solo magnitud ≥ 4.

### Edge Cases

- La fuente indica que el contenido no ha cambiado desde la consulta anterior: se registra la
  consulta como correcta sin novedades, no se guarda otro original y no se publica nada.
- La respuesta del feed llega vacía (cero elementos): es una consulta correcta con cero
  registros, no un fallo.
- Un evento del feed cambia de tipo entre versiones (de terremoto a otro tipo, o al revés): cada
  versión se trata según su propio tipo; la versión excluida queda en las exclusiones y las
  versiones de terremoto ya almacenadas no se borran.
- La fuente elimina un evento (deja de aparecer o lo marca como eliminado): no se borra nada
  del sistema.
- Un evento del catálogo ya existe porque llegó por el feed con una versión igual o más
  reciente: la versión del catálogo no se publica (una versión atrasada no es una novedad,
  enunciado §5.3 y FAQ 10) y el estado actual no cambia. La respuesta del catálogo que la
  contenía queda igualmente guardada como original.
- La fuente revisa un evento de 2025 entre dos ejecuciones de la carga: la segunda ejecución
  añade solo esa versión nueva.
- El total declarado por la fuente cambia durante la carga (el catálogo sigue vivo): la
  comprobación final lo detecta, lo indica y explica la diferencia en lugar de darla por buena.
- Un intervalo que, subdividido hasta el mínimo, sigue superando el máximo de la fuente: la
  carga se detiene con un error explícito; nunca acepta una respuesta truncada.
- El fichero de un intervalo ya descargado está dañado o su huella no coincide con la
  registrada: se vuelve a descargar ese intervalo.
- El broker o la base no están disponibles durante un ciclo: no se marca nada como publicado y
  el ciclo se reintenta. Si la base falla cuando la fuente ya ha respondido, el resultado
  obtenido se conserva y se registra en cuanto la base vuelve, antes de consultar de nuevo la
  fuente: la consulta no se pierde ni se repite.
- La parada coincide con el cambio de año: la recuperación de huecos no depende de la carga de
  2025 ni la sustituye.
- Un periodo cargado primero con magnitud ≥ 4 y recuperado después con todas las magnitudes:
  los eventos comunes no se duplican y los de menor magnitud se añaden.
- Se pide cargar un periodo que termina en el futuro o cuyo fin no es posterior a su inicio: la
  orden lo rechaza con un mensaje claro, sin consultar la fuente.
- Dos ejecuciones simultáneas de la carga histórica: pueden enviar dos veces el mismo mensaje,
  que el consumidor absorbe sin efecto; el resultado almacenado es el mismo que con una sola,
  sin eventos ni versiones duplicados y sin ficheros a medio escribir.

## Requirements *(mandatory)*

### Functional Requirements

**Registro de consultas y originales**

- **FR-001**: Toda consulta a USGS, al feed o al catálogo, correcta o fallida, MUST quedar
  registrada con su fuente, su propósito (en vivo, carga histórica o recuperación de huecos), la
  dirección consultada, el momento de inicio, la duración total, el número de intentos, el
  último código de respuesta, el resultado y, si falló, el detalle del error.
- **FR-001a**: Si el almacenamiento no está disponible cuando la fuente ya ha respondido, el
  resultado MUST conservarse y registrarse cuando vuelva a estarlo, antes de hacer otra consulta
  a la fuente; MUST NOT descartarse ni sustituirse por una consulta nueva.
- **FR-002**: El resultado de una consulta MUST ser uno de: correcta, sin cambios, error de
  respuesta, tiempo agotado, contenido ilegible o estructura no válida.
- **FR-003**: Cada consulta correcta MUST registrar el momento en que la fuente generó la
  respuesta y el reparto de sus elementos: recibidos, terremotos, excluidos y versiones
  publicadas; recibidos MUST ser igual a terremotos más excluidos.
- **FR-004**: El contenido original de cada respuesta MUST conservarse antes de transformarlo y
  MUST almacenarse una sola vez por contenido distinto. La identidad del contenido MUST
  calcularse sobre la colección de eventos y no sobre la cabecera de la respuesta, que cambia en
  cada consulta.
- **FR-005**: Cuando un contenido ya almacenado vuelve a recibirse, MUST actualizarse su fecha
  de última observación sin guardar otra copia.
- **FR-006**: Una respuesta ilegible o con estructura no válida MUST conservarse tal como se
  recibió, con la misma retención que los demás originales del feed, y MUST NOT publicarse
  ningún elemento suyo.

**Feed en vivo**

- **FR-007**: El sistema MUST consultar el feed de las últimas 24 horas a intervalos regulares
  configurables, de 60 segundos por defecto, sin depender de que el panel o la API estén en uso,
  y MUST NOT consultar la fuente con una frecuencia mayor que la configurada.
- **FR-008**: De cada respuesta MUST publicarse hacia el espacio real cada versión de terremoto
  que no se hubiera publicado antes, una vez por versión, identificando el feed como su
  procedencia y conservando el elemento original sin modificar.
- **FR-008a**: Cada mensaje publicado MUST usar el identificador del evento como clave y MUST
  incluir la fuente, el momento de ingesta, el modo (en vivo o reproducción; en esta
  funcionalidad siempre en vivo, también para el catálogo) y el evento original completo.
- **FR-009**: Una versión MUST marcarse como publicada solo después de que el broker confirme su
  recepción; si no hay confirmación, MUST volver a intentarse en un ciclo posterior.
- **FR-010**: Los elementos cuyo tipo no sea terremoto MUST NOT publicarse y MUST conservarse
  como exclusiones con su tipo, su motivo, su original y la consulta en la que se vieron por
  primera vez, una vez por versión.
- **FR-011**: Un elemento de una respuesta válida que no pueda identificarse (sin identificador
  o sin fecha de actualización legible) MUST NOT impedir el tratamiento del resto. MUST contarse
  entre los excluidos de la consulta, de modo que FR-003 se siga cumpliendo, y MUST quedar
  descrito en el registro de esa consulta (cuántos y en qué posición) y localizable en el
  original conservado. Al no tener identidad, MUST NOT guardarse como exclusión individual ni
  publicarse.
- **FR-012**: El sistema MUST NOT borrar ni modificar ningún evento, versión o exclusión porque
  deje de aparecer en la fuente.
- **FR-013**: Cuando la fuente indique que el contenido no ha cambiado, la consulta MUST
  registrarse como correcta sin cambios y MUST NOT generar publicaciones ni un nuevo original.
- **FR-014**: El momento de la última ingesta MUST poder obtenerse como el inicio de la consulta
  al feed más reciente con resultado correcto o sin cambios; MUST NOT avanzar con consultas
  fallidas ni depender de que hubiera eventos nuevos.

**Fallos de la fuente**

- **FR-015**: Ante saturación de la fuente o errores temporales del servidor, la consulta MUST
  reintentarse un número limitado de veces con espera creciente; cuando la fuente indique un
  tiempo de espera, la espera aplicada MUST NOT ser inferior.
- **FR-016**: Agotados los reintentos, la consulta MUST registrarse como fallida y el sistema
  MUST seguir funcionando e intentarlo de nuevo en el ciclo siguiente, sin reinicio manual.
- **FR-017**: Un fallo de la fuente MUST NOT alterar el estado de publicación ni los datos ya
  almacenados.

**Carga histórica**

- **FR-018**: El sistema MUST ofrecer un procedimiento documentado, ejecutable con una sola
  orden por una persona, que cargue en el espacio real los terremotos del catálogo histórico de
  USGS para un periodo y un filtro indicados (inicio incluido y fin excluido, en tiempo
  universal; magnitud mínima opcional). MUST NOT ejecutarse solo al arrancar el sistema.
- **FR-018a**: La carga obligatoria MUST ser la de todo el mundo con magnitud igual o superior a
  4 y tipo terremoto entre el 1 de enero de 2025 y el 1 de enero de 2026, y MUST poder lanzarse
  sin tener que escribir esos parámetros.
- **FR-018b**: El mismo procedimiento MUST permitir cargar el periodo del 1 de enero de 2026
  hasta la fecha actual con el mismo filtro, como ampliación documentada, y MUST rechazar con un
  mensaje claro un periodo que termine en el futuro o cuyo fin no sea posterior a su inicio.
- **FR-019**: El procedimiento MUST dividir el periodo en meses y, cuando un intervalo contenga
  más eventos de los que la fuente entrega en una respuesta, MUST subdividirlo; MUST NOT aceptar
  una respuesta truncada y MUST detenerse con un error explícito si no puede obtener un
  intervalo completo.
- **FR-020**: Los eventos que aparezcan en más de un intervalo MUST quedar almacenados una sola
  vez.
- **FR-021**: Cada petición al catálogo MUST registrarse con sus parámetros (intervalo, magnitud
  mínima y tipo), su resultado y su número de registros.
- **FR-022**: Los ficheros descargados MUST guardarse en la ubicación de datos situada fuera del
  control de versiones, y de cada uno MUST conservarse en la base su huella y su ruta. El
  repositorio MUST NOT contener ninguno.
- **FR-023**: Los eventos del histórico MUST llegar al espacio real por el mismo camino que los
  del feed (publicación, consumo y regla de versiones), por un canal propio distinto del de las
  novedades en vivo y del de la reproducción, e identificando el catálogo como su procedencia.
- **FR-024**: El procedimiento MUST ser reanudable: tras una interrupción, una nueva ejecución
  MUST completar la carga sin repetir los intervalos ya terminados, verificando por su huella
  los ficheros que reutilice.
- **FR-025**: El procedimiento MUST ser repetible: ejecutarlo de nuevo MUST NOT crear eventos ni
  versiones que ya existieran.
- **FR-026**: Al terminar, el procedimiento MUST mostrar y dejar registrado un resumen
  comprobable: eventos por intervalo, repeticiones entre intervalos, total de eventos distintos,
  total declarado por la fuente para el mismo filtro y la diferencia entre ambos; una
  diferencia distinta de cero MUST señalarse como tal.
- **FR-027**: Los elementos del catálogo cuyo tipo no sea terremoto, si la fuente devolviera
  alguno, MUST tratarse como exclusiones igual que en el feed.

**Recuperación de huecos**

- **FR-028**: Al arrancar, si existe una consulta correcta al feed y la más reciente es anterior
  al periodo que cubre el feed de 24 horas, el sistema MUST avisar de forma visible del periodo
  no cubierto y MUST mostrar la orden exacta que lo recupera.
- **FR-029**: La detección de un hueco MUST NOT impedir ni retrasar la consulta del feed en
  vivo, y MUST NOT lanzar la recuperación por su cuenta.
- **FR-030**: La recuperación MUST hacerse con el procedimiento de carga del catálogo (FR-018 a
  FR-027) para el periodo indicado, con el mismo alcance que el feed (todas las magnitudes), y
  sus consultas MUST registrarse con el propósito de recuperación de huecos.
- **FR-031**: Mientras exista un periodo detectado y no recuperado, MUST poder consultarse cuál
  es, y la documentación MUST explicar cómo recuperarlo y sus limitaciones (el catálogo se
  consulta como está en ese momento, no como estaba durante la parada).

- **FR-032**: Un sistema sin ninguna consulta previa al feed MUST NOT considerarse con hueco.

**Retención**

- **FR-033**: Los originales del feed cuya última observación supere la retención configurada,
  de 7 días por defecto, MUST eliminarse de forma periódica, al menos una vez al día. Cada
  purga MUST anotar en el registro de actividad del servicio (su log) cuántos originales
  eliminó; no se exige guardarlo en la base, y la evidencia de esta funcionalidad recoge el
  número y el tamaño observados.
- **FR-034**: La purga MUST NOT eliminar registros de consultas, exclusiones ni referencias a
  ficheros del catálogo histórico.

**Límites y evidencia**

- **FR-035**: Esta funcionalidad MUST NOT cambiar las reglas de validación del consumidor, la
  reproducción acelerada, el contrato de la API ni el panel, y MUST NOT modificar el modelo de
  datos de la spec 002 salvo necesidad demostrada, que MUST justificarse por escrito y
  reflejarse en el diccionario de datos.
- **FR-036**: La entrega MUST documentar el procedimiento de carga histórica y de regeneración
  de los ficheros, la recuperación de huecos, la retención de originales y el comportamiento
  ante fallos de la fuente. MUST documentar también las limitaciones del alcance: el histórico
  es una instantánea del catálogo en la fecha de extracción, y no se reconcilian los eventos que
  USGS elimina, fusiona o revisa cuando ya están fuera del feed (enunciado §4.2 y §5).
- **FR-036a**: La memoria MUST describir la respuesta del feed y del catálogo a partir de datos
  reales observados: estructura, tipo y unidad de cada campo utilizado, campos opcionales y con
  qué frecuencia faltan, frecuencia de actualización, errores encontrados y latencia observada
  de las consultas y de la publicación de los eventos por la fuente.
- **FR-036b**: La memoria MUST incluir el registro de procedencia: por cada conjunto (feed,
  histórico de 2025 y ampliaciones), fuente, periodo y filtros, fecha de extracción, consultas
  realizadas y número de registros; y MUST indicar qué periodos contienen todas las magnitudes y
  cuáles solo magnitud ≥ 4.
- **FR-037**: Cada historia MUST verificarse con el sistema real y dejar resultado esperado,
  resultado observado y salida en la carpeta de evidencias de esta funcionalidad; los fallos de
  la fuente MUST probarse con una fuente simulada, sin depender de que USGS falle.

### Key Entities *(include if feature involves data)*

Todas existen ya en el modelo de la spec 002; esta funcionalidad empieza a escribirlas.

- **Extracción**: una consulta a USGS, con su fuente, propósito, parámetros, resultado,
  intentos, duración y recuentos. Se conserva indefinidamente.
- **Original**: un contenido distinto recibido de la fuente, identificado por su huella. Los del
  feed se guardan comprimidos y caducan; los del catálogo son ficheros fuera del repositorio de
  los que se guarda huella y ruta.
- **Exclusión**: una versión de un elemento que no es un terremoto, con su tipo, motivo,
  original y la extracción en que se vio por primera vez.
- **Estado de publicación**: la última versión de cada evento cuya recepción confirmó el broker.
- **Canales de publicación**: uno para las novedades del feed y otro para el catálogo (carga
  histórica y recuperación de huecos); ambos terminan en el espacio real. El de reproducción no
  se usa aquí.
- **Evento y versión**: los escribe el consumidor a partir de lo publicado; esta funcionalidad
  solo determina qué se publica y con qué procedencia.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Durante una hora de funcionamiento continuo, el número de consultas al feed
  registradas coincide con el número de ciclos transcurridos (60 ± 1 con el intervalo por
  defecto), y ninguna consulta queda sin registro.
- **SC-002**: En el 100 % de las consultas correctas, elementos recibidos = terremotos +
  excluidos, y en ese mismo periodo el número de originales almacenados es igual al número de
  contenidos distintos recibidos.
- **SC-003**: Tras la carga histórica, la diferencia entre los terremotos de 2025 con magnitud
  ≥ 4 almacenados en el espacio real y el total declarado por la fuente para ese filtro en el
  momento de la extracción es cero, o está explicada evento a evento.
- **SC-004**: Repetir la carga histórica completa añade 0 eventos, y 0 versiones salvo las que
  la fuente haya revisado entre ambas ejecuciones.
- **SC-005**: Una carga interrumpida en cualquier punto y reanudada termina con los mismos
  recuentos que una carga sin interrupciones.
- **SC-006**: La carga histórica de 2025, desde que se lanza la orden hasta que esta termina
  (descarga, registro y publicación), tarda menos de 15 minutos en el equipo de referencia con
  una conexión doméstica. No incluye el tiempo que el consumidor necesita después para
  almacenar los eventos, que se anota aparte.
- **SC-007**: Tras una parada simulada de 36 horas, el arranque avisa del hueco en menos de un
  minuto con la orden de recuperación y, una vez ejecutada, el 100 % de los eventos que la
  fuente declara para el periodo perdido está almacenado, sin ningún evento duplicado.
- **SC-008**: En cada tipo de fallo simulado de la fuente (saturación, error de servidor, tiempo
  agotado, contenido ilegible y estructura no válida) consta el registro con su resultado e
  intentos, no se pierde ni se borra ningún dato, y el ciclo siguiente funciona sin intervención.
- **SC-009**: Con la fuente disponible, la antigüedad de la última ingesta no supera dos
  intervalos de consulta; durante una caída de la fuente no avanza. En ningún caso dos consultas
  al feed empiezan con menos separación que el intervalo configurado.
- **SC-010**: Tras una purga, no queda ningún original del feed sin observar desde hace más
  tiempo que la retención más un día, y se conserva el 100 % de los registros de consultas.
- **SC-011**: El repositorio entregado no contiene ningún fichero descargado de USGS, y la
  huella de cada fichero del histórico coincide con la registrada en la base.
- **SC-012**: Tras cargar 2026 hasta la fecha, la diferencia con el total declarado por la
  fuente es cero o está explicada, y el recuento de 2025 no ha cambiado.
- **SC-013**: El 100 % de los campos utilizados del feed y del catálogo aparece en la memoria
  con su tipo, su unidad y el porcentaje observado de ausencias.

## Assumptions

- La carga histórica la lanza una persona con una orden documentada; no se ejecuta sola al
  arrancar, para que el arranque no dependa de USGS y coincida con la «carga inicial» que
  describen las FAQ. Repetirla no duplica nada.
- La recuperación de huecos sigue la opción acordada el 2026-11-15: el sistema detecta el hueco
  y muestra la orden, y la persona la ejecuta. El enunciado solo exige explicar cómo se
  recupera; no se automatiza para no añadir complejidad que la rúbrica no valora.
- La recuperación usa el mismo alcance que el feed (todas las magnitudes y todos los tipos, con
  las exclusiones tratadas igual) para que la serie en vivo sea continua. No se fija un máximo
  de días: el periodo lo decide quien ejecuta la orden.
- La carga de 2026 (del 1 de enero hasta la fecha, magnitud ≥ 4) es una ampliación pedida para
  enriquecer el panel. Usa el mismo filtro que 2025 para que ambos años sean comparables; el
  espacio real contendrá entonces periodos con todas las magnitudes (feed y huecos recuperados)
  y periodos solo con magnitud ≥ 4, lo que la memoria debe indicar y el análisis (specs 006 y
  007) debe tener en cuenta comparando siempre con el mismo filtro.
- Los eventos del catálogo se publican con modo «en vivo» porque son datos reales destinados al
  espacio real; «reproducción» queda reservado a la spec 005.
- «Total declarado por la fuente» es el recuento que el propio catálogo de USGS ofrece para un
  filtro dado; se consulta en el momento de la carga y se registra junto al resumen.
- El catálogo de USGS sigue vivo: un evento de 2025 puede revisarse después de la carga. Volver
  a ejecutar el procedimiento es la forma de actualizarlo.
- El límite de eventos por respuesta del catálogo lo fija USGS (20.000 en el momento de
  redactar esto); el procedimiento no depende de la cifra exacta, sino de detectar que una
  respuesta alcanza el máximo.
- Reintentos por consulta: un número pequeño y configurable (3 por defecto) dentro del mismo
  ciclo; un ciclo fallido no se compensa con consultas adicionales.
- El mensaje publicado conserva el formato que hoy entiende el consumidor; cambiarlo
  corresponde a la spec 004.
- Desviación temporal heredada: hasta la spec 004 el consumidor envía a cuarentena los eventos
  sin magnitud, de modo que una parte de los eventos de pequeña magnitud recuperados en un hueco
  puede quedar en cuarentena. No se pierde: se reprocesa cuando la 004 corrija la regla. La
  carga de 2025 no se ve afectada porque todos sus eventos tienen magnitud ≥ 4.
- No se prevén cambios en el modelo de la spec 002: extracciones, originales, exclusiones,
  estado de publicación, purga e índice para la última ingesta ya existen.
- La última ingesta queda disponible en la base con esta funcionalidad; que la API la devuelva
  con el formato del contrato corresponde a la spec 006.
- Idioma: código, identificadores, ficheros y variables en inglés; documentación y evidencias
  en español (constitución v2.1.0).
- La rama parte de `002-platform-data-model`, que aún no está en `main`.
