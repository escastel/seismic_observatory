# Feature Specification: Plataforma y modelo de datos del observatorio

**Feature Branch**: `002-platform-data-model`

**Created**: 2026-11-14

**Status**: Draft

**Input**: User description: "Plataforma y modelo de datos del observatorio sísmico (base de todas las funcionalidades posteriores). Rehacer sobre el repositorio existente el despliegue de los cinco servicios obligatorios, el modelo de datos conceptual, lógico y físico con un único SQL de inicialización, el aislamiento de la reproducción histórica, la idempotencia por restricciones únicas, los índices justificados por medición, el diccionario de datos y la retirada de los grandes ficheros descargables del repositorio. Fuera de alcance: lógica de ingesta, validación, API y panel."

**Sustituye a**: las partes de despliegue y modelo de `specs/001-streaming-sismos-etl`, que queda
obsoleta por contradecir la constitución v2.0.0.

**Trazabilidad**: enunciado §2, §7, §9, §11 (reenviar versión, versión antigua, reinicio,
reproducción aislada), §12; CONTRATO-API «Transporte y contenedores»; FAQ 4, 12, 20, 28; guía de
entregables §1.2–1.4, §2.2, §2.5. Constitución: principios I, II, V, VI, IX.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Levantar el sistema desde un clon limpio (Priority: P1)

Como evaluador, quiero clonar el repositorio, crear la configuración local a partir del ejemplo y
arrancar todo el backend con una sola orden, para comprobar que el sistema es reproducible sin
adivinar pasos.

**Why this priority**: sin un arranque reproducible ninguna otra evidencia puede comprobarse; es
la condición de entrada de la entrega.

**Independent Test**: en un equipo sin volúmenes previos, seguir el README, ejecutar la orden de
arranque y verificar que los cinco servicios quedan en estado saludable y que la base de datos
contiene todos los objetos del modelo sin intervención manual.

**Acceptance Scenarios**:

1. **Given** un clon limpio y un `.env` creado desde `.env.example`, **When** se ejecuta
   `docker compose up --build -d`, **Then** productor, Kafka, consumidor, PostgreSQL y API
   alcanzan el estado saludable en menos de tres minutos, medidos con las imágenes ya
   construidas; la primera construcción queda cubierta por SC-001.
2. **Given** el sistema arrancado, **When** se inspeccionan los puertos del equipo, **Then** solo
   la API es accesible y únicamente desde el propio equipo; Kafka y PostgreSQL no lo son.
3. **Given** que PostgreSQL o Kafka tardan en estar disponibles, **When** arrancan los servicios
   Python, **Then** reintentan la conexión con espera y acaban saludables sin reinicio manual.
4. **Given** datos ya almacenados, **When** se detienen y vuelven a arrancar los servicios,
   **Then** los datos y el estado de publicación se conservan.
5. **Given** el repositorio entregado, **When** se revisa su contenido, **Then** no contiene
   credenciales, volúmenes, `node_modules` ni conjuntos descargables grandes.

---

### User Story 2 - Un modelo que impide duplicar y retroceder (Priority: P1)

Como responsable de datos, quiero que la propia base de datos garantice una fila por terremoto,
una fila por versión observada y que una versión antigua no sustituya a una más reciente, para
que repetir mensajes tras un fallo no altere los resultados.

**Why this priority**: es el núcleo del criterio de modelado y la base de cuatro pruebas de
aceptación.

**Independent Test**: aplicar directamente sobre la base la secuencia de la FAQ 12 (primera
versión, repetición, revisión posterior, versión antigua tardía, otro terremoto) y comprobar los
recuentos tras cada paso.

**Acceptance Scenarios**:

1. **Given** una base vacía, **When** se registra la primera versión de E1, **Then** hay 1 evento
   actual y 1 versión.
2. **Given** E1 registrado, **When** se registra otra vez la misma versión, **Then** siguen
   existiendo 1 evento actual y 1 versión.
3. **Given** E1 con `updated` 10:05, **When** llega una revisión con `updated` 10:09 y magnitud
   distinta, **Then** hay 1 evento actual con los datos nuevos y 2 versiones.
4. **Given** E1 actualizado a 10:09, **When** llega tarde la versión de 10:05, **Then** el evento
   actual no cambia y siguen existiendo 2 versiones.
5. **Given** un evento con magnitud, tipo de magnitud o profundidad ausentes, **When** se
   registra, **Then** se almacena con esos campos vacíos, sin sustituirlos por cero.
6. **Given** un evento situado en el mar, **When** se registra, **Then** se almacena sin país y
   sigue contando en los totales.
7. **Given** un intento de registrar coordenadas fuera de rango en el estado actual, **When** se
   ejecuta, **Then** la base lo rechaza.

---

### User Story 3 - Reproducción físicamente separada de los datos reales (Priority: P2)

Como responsable de la demostración, quiero que los datos de la reproducción histórica vivan en
un espacio propio con la misma estructura, para que nunca puedan modificar ni mezclarse con los
datos reales.

**Why this priority**: el aislamiento es obligatorio en el enunciado y condiciona el diseño de
consumidor, API y panel.

**Independent Test**: registrar el mismo identificador de evento en el espacio real y en el de
reproducción con valores distintos y comprobar que cada espacio conserva los suyos y que los
recuentos reales no cambian.

**Acceptance Scenarios**:

1. **Given** un evento real E1, **When** se registra E1 en el espacio de reproducción con otra
   magnitud, **Then** el E1 real conserva su magnitud y su recuento no varía.
2. **Given** datos en el espacio de reproducción, **When** se vacía ese espacio, **Then** los
   datos reales, el catálogo de países y el estado de publicación real permanecen intactos.
3. **Given** un evento de reproducción, **When** se consulta, **Then** conserva su tiempo de
   ocurrencia original y además el instante en que se reprodujo.

---

### User Story 4 - Trazabilidad del original y de las extracciones (Priority: P2)

Como autora de la memoria, quiero que cada extracción quede registrada y cada versión guarde su
original, para poder reconstruir qué datos se usaron y de dónde proceden.

**Why this priority**: sostiene los criterios de extracción y calidad y el registro de
procedencia exigido.

**Independent Test**: registrar dos extracciones con contenido idéntico y una distinta y comprobar
que hay tres extracciones registradas y solo dos originales almacenados.

**Acceptance Scenarios**:

1. **Given** dos extracciones con el mismo contenido, **When** se registran, **Then** ambas
   constan en el registro pero el original se almacena una sola vez.
2. **Given** una extracción fallida, **When** se registra, **Then** queda constancia del error y
   no se pierde el último estado válido.
3. **Given** un registro rechazado, **When** se consulta la cuarentena, **Then** constan el
   motivo, el momento y una referencia al original.
4. **Given** un elemento excluido por no ser un terremoto, **When** se consulta, **Then** consta
   su tipo y el motivo de exclusión.
5. **Given** cinco mensajes recibidos de los que uno es una repetición, **When** se consulta el
   registro de mensajes, **Then** constan los cinco con su resultado, de modo que se pueden
   contar mensajes recibidos, versiones distintas y eventos actuales por separado.

---

### User Story 5 - Modelo explicado y optimizado con mediciones (Priority: P3)

Como evaluador, quiero un diccionario de datos, el modelo en sus tres niveles y la justificación
medida de cada índice, para valorar el modelado en el nivel sobresaliente.

**Why this priority**: diferencia «modelo correcto» de «modelo optimizado» en la rúbrica, pero
depende de que el modelo exista.

**Independent Test**: leer la documentación y repetir la medición sin y con índice sobre un
conjunto sintético etiquetado, obteniendo la misma conclusión documentada.

**Acceptance Scenarios**:

1. **Given** la documentación, **When** se busca cualquier campo del modelo, **Then** aparece su
   significado, tipo o unidad y tratamiento de ausencias.
2. **Given** cada índice definido, **When** se revisa su justificación, **Then** nombra la
   consulta que resuelve y aporta una medición sin y con índice en al menos tres tamaños.
3. **Given** datos sintéticos creados para medir, **When** se analiza la sismicidad real,
   **Then** esos datos no intervienen.

### Edge Cases

- Dos entidades del catálogo geográfico con el mismo identificador: la carga falla de forma
  explícita en lugar de elegir una.
- Un evento cuyo tiempo de ocurrencia cambia de día en una revisión: su fecha asociada se
  actualiza con él.
- Arranque con un volumen creado por una versión anterior del modelo: el procedimiento
  documentado indica cómo recrearlo; no se intenta migrar en silencio.
- Un servicio Python arranca antes de que exista el topic o la tabla que necesita: reintenta y
  no queda en un bucle de fallos sin espera.
- El contenedor del túnel no está configurado: los cinco servicios obligatorios arrancan igual.
- Una versión de un evento que nunca llegó a ser válida (solo cuarentena): no genera fila de
  estado actual ni altera recuentos.

## Requirements *(mandatory)*

### Functional Requirements

**Despliegue**

- **FR-001**: El sistema MUST arrancar productor, Kafka, consumidor, PostgreSQL y API como cinco
  servicios separados con la orden `docker compose up --build -d`, sin pasos manuales
  posteriores para crear tablas o topics.
- **FR-002**: Cada uno de los cinco servicios MUST declarar una comprobación de salud que
  refleje su capacidad real de trabajar, y los servicios dependientes MUST esperar a que sus
  dependencias estén saludables.
- **FR-003**: Los servicios Python MUST reintentar con espera progresiva la conexión a Kafka y a
  PostgreSQL, tanto al arrancar como tras una pérdida de conexión, y MUST reiniciarse
  automáticamente si terminan de forma inesperada.
- **FR-004**: Los datos de PostgreSQL y de Kafka MUST persistir entre reinicios de los
  servicios.
- **FR-005**: Kafka MUST tener una retención limitada y documentada, y los topics necesarios
  MUST crearse de forma explícita al arrancar.
- **FR-006**: Solo la API MUST ser accesible desde fuera de la red interna, y únicamente desde
  el propio equipo; Kafka y PostgreSQL MUST NOT publicar puertos.
- **FR-007**: El túnel HTTPS MUST poder ejecutarse como servicio adicional opcional que apunta a
  la API por su nombre de servicio, sin formar parte de los cinco obligatorios ni del proceso de
  la API, y su ausencia MUST NOT impedir el arranque.
- **FR-008**: Todas las dependencias MUST estar fijadas a versión exacta y las dependencias no
  utilizadas MUST eliminarse.
- **FR-009**: El repositorio MUST incluir un `.env.example` con todas las variables requeridas,
  nombres coincidentes con el código y sin credenciales reales; el origen permitido para el
  panel MUST configurarse como lista explícita, sin comodín.
- **FR-010**: El repositorio MUST NOT versionar conjuntos descargables grandes; MUST documentar
  dónde se guardan los originales y cómo regenerarlos.

**Modelo de datos**

- **FR-011**: El modelo MUST definirse en un único conjunto ordenado de sentencias de
  inicialización que sea la única fuente de la estructura; los servicios MUST NOT crear ni
  alterar tablas por su cuenta.
- **FR-012**: El estado actual MUST contener exactamente una fila por identificador de evento,
  con tiempo de ocurrencia, tiempo de actualización en la fuente y tiempo de ingesta en UTC,
  coordenadas, y magnitud, tipo de magnitud, profundidad, descripción de lugar y país anulables.
- **FR-013**: El estado actual MUST rechazar longitudes fuera de [−180, 180] y latitudes fuera
  de [−90, 90], y MUST aceptar magnitudes y profundidades negativas.
- **FR-014**: El historial MUST contener exactamente una fila por par identificador de evento y
  tiempo de actualización, con el original recibido y el momento de recepción.
- **FR-015**: El modelo MUST ofrecer una operación de escritura que, de forma atómica, registre
  la versión si es nueva y actualice el estado actual solo si la versión es estrictamente más
  reciente que la almacenada.
- **FR-016**: La dimensión de país MUST contener una fila por entidad del catálogo entregado,
  identificada por `ADM0_A3`, con nombre en español, nombre administrativo, continente y
  subregión, y su carga MUST fallar si el identificador no es único. La ausencia de país se
  representa con país vacío, no con una fila ficticia.
- **FR-017**: La dimensión de fecha MUST contener una fila por día UTC con sus atributos de
  calendario, y cubrir sin huecos el periodo histórico y el actual, incluidos los días sin
  eventos.
- **FR-018**: La cuarentena MUST conservar cada rechazo con código de motivo, detalle, momento,
  procedencia del mensaje y el original completo, y MUST evitar duplicar el mismo rechazo cuando
  un mensaje se reprocesa.
- **FR-019**: El modelo MUST conservar las exclusiones por tipo de evento distinto de terremoto
  con su tipo y motivo.
- **FR-020**: El estado de publicación del productor MUST conservar, por identificador, la
  última versión publicada y sobrevivir a reinicios.
- **FR-021**: El registro de extracciones MUST conservar por cada consulta la fuente, la URL o
  parámetros, el momento, el resultado, el número de registros y una huella del contenido, y
  MUST almacenar una sola vez los originales idénticos, con una retención definida.
- **FR-022**: Cada fila de estado actual y de historial MUST indicar su procedencia (feed
  reciente o catálogo histórico).
- **FR-031**: El modelo MUST registrar una vez cada mensaje procesado por el consumidor, con su
  posición en el transporte, el evento y la versión a los que se refiere, el resultado obtenido
  (nuevo, revisión, repetición, versión atrasada o cuarentena), el momento en que el productor lo
  publicó y el momento en que se procesó. Reprocesar un mensaje MUST NOT añadir otro registro.
  Este registro es una auditoría de la ingesta: los recuentos de terremotos MUST seguir
  calculándose desde el estado actual.

**Aislamiento**

- **FR-023**: La reproducción MUST disponer de un espacio separado con la misma estructura de
  estado actual, historial, cuarentena, exclusiones, estado de publicación y registro de
  mensajes, de forma que el mismo identificador pueda existir en ambos espacios sin interferir.
- **FR-024**: El espacio de reproducción MUST registrar además el instante de reproducción de
  cada evento y MUST poder vaciarse sin afectar a los datos reales.
- **FR-025**: Los datos sintéticos de las mediciones MUST almacenarse fuera de los espacios real
  y de reproducción y eliminarse tras medir.

**Optimización y documentación**

- **FR-026**: El modelo MUST evaluar un índice para cada consulta prevista (intervalo de tiempo
  de ocurrencia, país, magnitud mínima y versiones por identificador) e incluir los que superen
  la medición de FR-027; cada índice incluido MUST justificarse por la consulta que resuelve y
  cada índice descartado MUST quedar documentado con su medición.
- **FR-027**: La entrega MUST incluir una medición reproducible de tiempo sin y con índice en al
  menos tres tamaños de entrada, indicando equipo y procedimiento, y MUST retirar los índices
  cuya consulta no sea al menos 2 veces más rápida en mediana en el tamaño mayor.
- **FR-028**: La entrega MUST incluir el modelo conceptual, lógico y físico, explicando qué
  representa una fila de cada tabla, las claves, las relaciones y las restricciones.
- **FR-029**: La entrega MUST incluir un diccionario de datos con significado, tipo o unidad,
  conversión aplicada y tratamiento de ausencias de cada campo utilizado.
- **FR-030**: El README MUST explicar requisitos, configuración, arranque, comprobación de
  estado y logs, parada, qué se conserva al reiniciar y cómo recrear la base desde cero.

### Key Entities *(include if feature involves data)*

- **Evento actual**: la versión más reciente conocida de un terremoto; una fila por
  identificador. Se relaciona opcionalmente con un país y siempre con una fecha.
- **Versión de evento**: una versión observada de un terremoto, identificada por evento y tiempo
  de actualización, con su original.
- **País**: entidad del catálogo Natural Earth identificada por `ADM0_A3`, con nombre,
  continente y subregión.
- **Fecha**: día UTC con atributos de calendario; permite contar días sin eventos.
- **Cuarentena**: registro no tratable, con motivo y original.
- **Exclusión**: elemento de la fuente que no es un terremoto, con su tipo y motivo.
- **Estado de publicación**: última versión de cada evento que el productor ha publicado.
- **Mensaje procesado**: un mensaje recibido por el consumidor y lo que ocurrió con él; es el
  denominador «mensajes recibidos» del apartado de calidad.
- **Extracción**: una consulta a la fuente con sus metadatos y resultado.
- **Original almacenado**: contenido íntegro de una respuesta, guardado una vez por contenido
  distinto.
- **Espacio de reproducción**: réplica estructural de evento actual, versión, cuarentena,
  exclusión, estado de publicación y mensaje procesado para datos reproducidos.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Una persona ajena al proyecto levanta los cinco servicios en estado saludable en
  menos de 10 minutos siguiendo solo el README, sin consultar al equipo.
- **SC-002**: Tras 10 arranques consecutivos desde cero, los cinco servicios alcanzan el estado
  saludable en las 10 ocasiones sin intervención manual.
- **SC-003**: La secuencia de cinco mensajes de la FAQ 12 produce exactamente 2 eventos actuales
  y 3 versiones, con E1 en su magnitud revisada.
- **SC-004**: Reprocesar 1.000 veces un mismo conjunto de versiones no modifica ningún recuento
  de eventos, versiones ni rechazos.
- **SC-005**: Registrar y vaciar 10.000 eventos de reproducción deja sin ningún cambio los
  recuentos y valores de los datos reales.
- **SC-006**: El 100 % de los campos del modelo aparece en el diccionario de datos con
  significado, unidad y tratamiento de ausencias.
- **SC-007**: Cada índice conservado hace su consulta al menos 2 veces más rápida en mediana en
  el mayor de los tres tamaños probados.
- **SC-008**: Un análisis de puertos desde otro dispositivo de la red no encuentra accesibles ni
  la base de datos ni el broker.
- **SC-009**: El repositorio entregado no contiene ningún fichero de datos mayor de 5 MB salvo
  el catálogo geográfico proporcionado.

## Assumptions

- La base de datos actual solo contiene unas decenas de eventos de prueba: se recrea desde cero
  y no se migra.
- El histórico de 2025 (mundial, magnitud ≥ 4, tipo terremoto) se almacena en el espacio real,
  distinguido por su procedencia; es dato real, no reproducción.
- Retención por defecto: 7 días para los mensajes de Kafka y 7 días para los originales del
  feed; los originales del catálogo histórico se conservan como ficheros fuera de Git.
- El fichero `db/seeds/historical_2026.jsonl` (99 MB) se ha eliminado del historial de Git con
  aprobación expresa (2026-11-14); queda en local, ignorado. Los nuevos conjuntos descargados
  se guardan en `data/`, fuera de Git.
- Alcance del histórico: el obligatorio es 2025, mundial, magnitud ≥ 4. Cargar el catálogo
  completo para enriquecer el panel es una ampliación posterior que el modelo no debe impedir.
- Idioma: tablas, columnas, esquemas, topics, variables y nombres de fichero en inglés;
  documentación en español (constitución v2.1.0).
- El catálogo geográfico es la copia entregada (177 entidades, `ADM0_A3` único, verificado con
  la huella de `FUENTES-Y-LICENCIAS.md`); no se sustituye por otra versión.
- La integración espacial se realiza en el consumidor; la base no necesita capacidades
  geoespaciales propias.
- La lógica de ingesta, validación, API y panel se especifica en funcionalidades posteriores
  (003–008); en esta, los servicios existentes solo deben seguir arrancando contra el modelo
  nuevo, aunque su comportamiento todavía no cumpla el enunciado. Excepción: las dos garantías
  de offset del principio II (empezar desde el principio del topic y no avanzar tras un fallo)
  se corrigen aquí, porque sin ellas el recorrido de extremo a extremo no es fiable.
- Desviación temporal conocida: hasta la spec 004 el consumidor sigue enviando la magnitud nula
  a cuarentena, en contra del principio III. El modelo ya la admite; la rama no llega a `main`
  antes de corregirlo.
- El espacio de reproducción comparte las dimensiones de país y fecha con el espacio real por
  ser datos de referencia inmutables.
