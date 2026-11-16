# Feature Specification: Reproducción acelerada de una selección histórica

**Feature Branch**: `005-historical-replay`

**Created**: 2026-11-16

**Status**: Draft

**Input**: User description: "Spec 005: reproducción acelerada de una selección histórica, sobre la plataforma (002), la ingesta (003) y el consumidor (004). Objetivo: poder demostrar el sistema con actividad aunque no ocurra ningún terremoto durante la defensa, reproduciendo a velocidad acelerada una selección histórica por Kafka, sin mezclarla nunca con los datos reales (enunciado §11, prueba «Reproducción histórica» y el párrafo sobre la reproducción acelerada; FAQ 32; principio VI de la constitución). Cubre la selección desde lo ya descargado, la orden de reproducción con velocidad configurable y control (pausar, reanudar, detener, repetir), el aislamiento comprobable respecto de `core`, los casos sintéticos controlados de duplicado, revisión, versión antigua y cuarentena, el destino del material heredado y la evidencia con el sistema real. Fuera de alcance: contrato de la API y etiquetado «REPRODUCCIÓN» (006), panel (007) y análisis (008). Sin cambios en el modelo de las specs 002 a 004 salvo necesidad demostrada y justificada."

**Depende de**: `specs/002-platform-data-model` (esquema `replay`, `replay.reset()`, propósito
`replay_selection`, regla de `replayed_at`), `specs/003-usgs-ingestion` (catálogo descargado en
`data/usgs/catalog/` y su registro) y `specs/004-consumer-quality` (reglas del consumidor,
convención de datos sintéticos).

**Trazabilidad**: enunciado §11 (prueba «Reproducción histórica» y párrafo sobre la reproducción
acelerada), FAQ 32, constitución principio VI (topic propio, esquema separado, mismo código del
consumidor, tiempo original conservado más tiempo de reproducción, sin alterar fechas, etiqueta
«REPRODUCCIÓN») y principios III, V, VII y IX.

**Prueba de aceptación del enunciado (§11) que esta funcionalidad sostiene**: «Reproducción
histórica»: una selección histórica se reproduce acelerada, el panel (spec 007) la muestra como
«REPRODUCCIÓN» y los datos reales no cambian. Aquí se garantiza la parte de datos: circulación,
aislamiento e identificabilidad. El etiquetado visual y de la API quedan fuera de alcance.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reproducir una selección histórica sin tocar los datos reales (Priority: P1)

Como persona que defiende el proyecto, quiero elegir un periodo, una magnitud mínima y, si
quiero, una zona del histórico ya descargado y reproducirlo a la velocidad que indique, para
mostrar actividad continua aunque no ocurra ningún terremoto durante la defensa, con la garantía
de que los datos reales no se alteran.

**Why this priority**: es el objetivo de la funcionalidad y la prueba «Reproducción histórica»
del enunciado; sin ella no hay demostración posible sin sismos reales.

**Independent Test**: con el catálogo ya descargado, ejecutar una reproducción de al menos
5.000 eventos a velocidad acelerada y comparar, antes y después, recuentos y suma de
comprobación de todas las tablas de datos reales, y los recuentos del espacio de reproducción
con el número de eventos de la selección.

**Acceptance Scenarios**:

1. **Given** el catálogo descargado, **When** se solicita una selección por periodo y magnitud
   mínima, **Then** se obtiene la lista de eventos ordenada por tiempo de ocurrencia sin volver
   a consultar a USGS, y queda registrada como consulta con propósito de selección de
   reproducción, con sus parámetros y el número de eventos seleccionados.
2. **Given** una selección con filtro de zona, **When** se obtiene, **Then** solo incluye
   eventos de esa zona; sin filtro de zona incluye todos los del periodo y magnitud.
3. **Given** una selección registrada, **When** se ordena reproducirla con una velocidad
   indicada en eventos por segundo, **Then** los eventos se publican en el topic de
   reproducción, en orden de tiempo de ocurrencia, con modo «reproducción» y clave igual al
   identificador del evento, a una cadencia cercana a la pedida.
4. **Given** una reproducción con factor de aceleración sobre el tiempo original, **When** se
   ejecuta, **Then** el intervalo entre publicaciones es el intervalo original entre eventos
   dividido por el factor, y si además se indica una cadencia máxima en eventos por segundo,
   esta no se supera.
5. **Given** una reproducción terminada, **When** se consulta la base, **Then** cada evento
   publicado está en el espacio de reproducción con su tiempo de ocurrencia original intacto y
   con el instante de reproducción informado; ninguna fecha se ha desplazado hacia el presente.
6. **Given** que el mismo identificador existe en los datos reales y en la reproducción,
   **When** se reproduce, **Then** ambos coexisten con valores propios y ninguno modifica al
   otro.
7. **Given** una reproducción de miles de eventos, **When** termina, **Then** recuentos y suma
   de comprobación de todas las tablas de datos reales son idénticos a los de antes.

---

### User Story 2 - Controlar la reproducción durante la demostración (Priority: P1)

Como persona que defiende el proyecto, quiero pausar, reanudar, detener y repetir desde cero la
reproducción, para adaptarme a las preguntas del tribunal y volver a mostrar la demostración
sin preparar nada.

**Why this priority**: una demostración en directo no puede ser un proceso que solo corre hasta
el final; el reinicio desde cero es lo que la hace repetible.

**Independent Test**: lanzar una reproducción, pausarla, comprobar que no llegan eventos,
reanudarla, detenerla, vaciar el espacio de reproducción y repetirla, comprobando en cada paso
el estado de la base y que los datos reales no cambian.

**Acceptance Scenarios**:

1. **Given** una reproducción en curso, **When** se pausa, **Then** no se publican más eventos
   hasta reanudar y, al reanudar, continúa por el siguiente evento sin saltarse ni repetir.
2. **Given** una reproducción en curso o en pausa, **When** se detiene, **Then** no se publica
   nada más, lo ya publicado se conserva y queda constancia de cuántos eventos se enviaron.
3. **Given** una reproducción terminada o detenida, **When** se repite desde cero, **Then** el
   espacio de reproducción se vacía con la operación de reinicio del modelo, la selección se
   publica de nuevo y el resultado final es idéntico al de la primera vez; los datos reales
   no cambian.
4. **Given** una orden de reinicio, **When** se ejecuta, **Then** solo se vacían las tablas de
   reproducción; no existe ni se usa una operación equivalente sobre los datos reales.

---

### User Story 3 - Casos controlados de duplicado, revisión y cuarentena dentro de la reproducción (Priority: P2)

Como persona que defiende el proyecto, quiero que la reproducción incluya, marcados como
sintéticos, un conjunto pequeño de casos con resultado conocido, para demostrar en directo cómo
trata el sistema la primera versión, la repetición exacta, la revisión posterior, la versión
antigua tardía y el mensaje irrecuperable.

**Why this priority**: demuestra las reglas de idempotencia y calidad con un resultado
esperado que se comprueba con consultas, pero el histórico real ya sostiene la demostración
sin ellos.

**Independent Test**: reproducir solo el conjunto sintético y comprobar con consultas el
resultado esperado de cada caso.

**Acceptance Scenarios**:

1. **Given** el conjunto sintético, **When** se reproduce, **Then** cada caso tiene
   identificador con prefijo `synthetic-` y la marca `synthetic` y cada uno termina como se
   espera: primera versión (nueva), repetición exacta (`duplicate`, sin cambio de recuentos),
   revisión posterior (`revised`, el estado actual toma la versión nueva y el historial
   conserva ambas), versión antigua tardía (`stale`, el estado actual no retrocede) y un caso
   que va a cuarentena con su motivo.
2. **Given** una reproducción que incluye los casos sintéticos, **When** se consulta el
   espacio de reproducción, **Then** los sintéticos se distinguen de los eventos reales
   reproducidos y pueden excluirse con una condición simple.
3. **Given** los casos sintéticos, **When** se reproducen, **Then** nunca llegan a los datos
   reales.

---

### User Story 4 - Resistir un reinicio del consumidor a mitad de la reproducción (Priority: P2)

Como persona que defiende el proyecto, quiero que, si el consumidor se reinicia mientras se
reproduce, el resultado final sea el mismo que sin reinicio, para que un fallo no invalide la
demostración.

**Why this priority**: es la combinación de la prueba «Reiniciar consumidor» con la
reproducción y valida que se reutiliza el mismo código sin bifurcaciones.

**Independent Test**: reiniciar el consumidor a mitad de una reproducción de al menos 5.000
eventos y comparar recuentos y resumen del espacio de reproducción con los de una ejecución sin
reinicio.

**Acceptance Scenarios**:

1. **Given** una reproducción en curso, **When** se reinicia el consumidor, **Then** reanuda
   sin pérdidas ni duplicados de efecto y al terminar el recuento coincide con el número de
   eventos distintos de la selección.

---

### User Story 5 - Preparar la demostración de la defensa con instrucciones reproducibles (Priority: P3)

Como persona que defiende el proyecto, quiero un procedimiento paso a paso en el README y un
apartado en la memoria, con evidencia de que funciona, y que el material heredado de pruebas
tenga un destino claro, para poder ejecutar la demostración sin improvisar y que la entrega sea
coherente.

**Why this priority**: sin documentación y evidencia la funcionalidad no es evaluable; depende
de que las historias anteriores funcionen.

**Independent Test**: seguir el procedimiento del README desde un entorno recién levantado y
llegar a la reproducción completada sin pasos no documentados.

**Acceptance Scenarios**:

1. **Given** el README, **When** una persona sigue los pasos desde un sistema levantado,
   **Then** llega a una reproducción en curso y sabe cómo comprobar aislamiento y cómo
   repetirla.
2. **Given** los lotes heredados de `db/seeds/`, **When** se revisa el repositorio, **Then**
   cada uno está sustituido por la selección real o conservado con nombre que indica que es un
   lote mínimo de prueba, y el motivo queda documentado; ningún conjunto descargado está en Git.
3. **Given** `docs/evidence/005/`, **When** se consulta, **Then** contiene, con resultado
   esperado y observado sobre el sistema real: reproducción de al menos 5.000 eventos
   acelerada, comprobación de aislamiento, reinicio del consumidor a mitad y repetición tras
   reinicio del espacio de reproducción.

---

### Edge Cases

- Selección vacía (periodo sin eventos, magnitud demasiado alta o zona inexistente): la orden
  informa de que no hay eventos, no publica nada y queda registrada con 0 eventos.
- Fichero del catálogo ausente o con huella que no coincide con su registro: la selección falla
  con un mensaje claro en lugar de reproducir datos parciales.
- Selección con eventos de magnitud nula o con otras anomalías: se reproducen y reciben el
  mismo tratamiento que en datos reales (principio III).
- Velocidad inválida (cero, negativa, no numérica): se rechaza antes de publicar.
- Se ordena reproducir mientras ya hay una reproducción en curso: se rechaza o se avisa; nunca
  corren dos a la vez mezclando efectos.
- Reproducción con el espacio de reproducción ya poblado y sin reiniciar: el resultado sigue
  siendo idempotente (repeticiones exactas, sin aumentar recuentos).
- Kafka o el consumidor no disponibles durante la reproducción: la orden falla o se pausa con
  información clara y puede reanudarse sin duplicar efectos.
- Un evento del topic de reproducción no debe poder terminar en el esquema real, ni uno del
  topic real en el de reproducción.
- Zona indicada que el catálogo no permite resolver: la orden lo indica y no la ignora en
  silencio.

## Requirements *(mandatory)*

### Functional Requirements

**Selección**

- **FR-001**: El sistema MUST obtener la selección exclusivamente de los ficheros ya descargados
  del catálogo histórico, sin consultar a USGS.
- **FR-002**: La selección MUST admitir filtro por periodo y magnitud mínima, y opcionalmente
  por zona, y MUST devolverse ordenada por tiempo de ocurrencia.
- **FR-003**: Cada selección MUST quedar registrada como consulta con propósito de selección de
  reproducción, con sus parámetros y el número de eventos, y MUST poder localizarse por SQL.
- **FR-004**: El sistema MUST verificar que los ficheros usados coinciden con los registrados
  (principio V) y MUST fallar sin reproducir parcialmente si no coinciden.

**Reproducción y control**

- **FR-005**: Una orden MUST publicar la selección en el topic de reproducción con modo
  «reproducción» y clave igual al identificador del evento.
- **FR-006**: La orden MUST aceptar una velocidad en eventos por segundo y, opcionalmente, un
  factor de aceleración sobre el tiempo original; si se dan ambos, la cadencia MUST no superar
  la velocidad indicada.
- **FR-007**: Cada mensaje MUST conservar el tiempo de ocurrencia original y añadir el instante
  de reproducción; el sistema MUST NOT alterar fechas para que parezcan recientes.
- **FR-008**: La reproducción MUST poder pausarse, reanudarse y detenerse, y MUST informar de
  cuántos eventos se han publicado y cuántos faltan.
- **FR-009**: Repetir desde cero MUST vaciar el espacio de reproducción mediante la operación
  de reinicio del modelo y MUST NOT afectar a los datos reales.
- **FR-010**: Solo una reproducción MUST estar activa a la vez.

**Aislamiento**

- **FR-011**: Los eventos reproducidos MUST persistirse solo en el esquema de reproducción, por
  el mismo consumidor y con las mismas reglas de la spec 004, sin bifurcar su código.
- **FR-012**: Un mismo identificador MUST poder existir en datos reales y en reproducción con
  valores distintos sin interferir.
- **FR-013**: Antes y después de una reproducción de miles de eventos, el recuento y una suma de
  comprobación de cada tabla de datos reales MUST ser idénticos, y el sistema MUST ofrecer una
  forma de comprobarlo.
- **FR-014**: Todo dato reproducido MUST ser identificable como tal desde la base mediante el
  esquema, el instante de reproducción y el modo en el mensaje, de forma que las specs 006 y
  007 puedan etiquetarlo «REPRODUCCIÓN». El etiquetado queda fuera de alcance.
- **FR-015**: Los eventos del topic real MUST NOT acabar en el esquema de reproducción ni los
  del topic de reproducción en el real.

**Casos sintéticos**

- **FR-016**: La reproducción MUST poder incluir un conjunto de casos sintéticos con la
  convención de la spec 004 (identificador `synthetic-` y marca `synthetic`): primera versión,
  repetición exacta, revisión posterior, versión antigua tardía y un caso a cuarentena.
- **FR-017**: El resultado esperado de cada caso sintético MUST comprobarse con consultas y
  constar en la evidencia.
- **FR-018**: Los casos sintéticos MUST NOT llegar a los datos reales y MUST poder excluirse
  del análisis.

**Material heredado y entrega**

- **FR-019**: El sistema MUST resolver el destino de `producer/app/replay.py`,
  `db/seeds/historical_2025.jsonl` y `db/seeds/historical_1900.jsonl`: sustituirlos por la
  selección real y documentar el procedimiento, o conservarlos renombrados como lotes mínimos de
  prueba. Ningún conjunto descargado MUST versionarse.
- **FR-020**: `docs/evidence/005/` MUST contener resultados esperado/observado con el sistema
  real de: reproducción de al menos 5.000 eventos acelerada, aislamiento, reinicio del
  consumidor a mitad y repetición tras reinicio.
- **FR-021**: La memoria (`docs/report.md`) y el README MUST describir paso a paso cómo ejecutar
  la demostración de la defensa.
- **FR-022**: Las pruebas MUST ser de comportamiento y la verificación MUST hacerse con el
  sistema real.

### Key Entities *(include if feature involves data)*

- **Selección de reproducción**: lista ordenada de eventos del catálogo descargado, definida por
  periodo, magnitud mínima y zona opcional; se registra como consulta con su número de eventos.
- **Orden de reproducción**: ejecución de una selección con velocidad, factor de aceleración
  opcional y estado (en curso, en pausa, detenida, terminada) y contadores de enviados y
  pendientes.
- **Mensaje de reproducción**: evento con el tiempo original, el modo «reproducción» y el
  instante de reproducción.
- **Conjunto sintético de reproducción**: casos con resultado esperado conocido, marcados como
  sintéticos.
- **Espacio de reproducción**: datos persistidos de reproducción, separados de los reales y
  vaciables sin afectarlos.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Una persona obtiene una reproducción en marcha de la selección elegida en menos de
  5 minutos siguiendo el README, sin pasos no documentados.
- **SC-002**: Una reproducción de al menos 5.000 eventos termina con el recuento del espacio de
  reproducción igual al de eventos distintos de la selección, a una cadencia dentro del ±20 %
  de la pedida.
- **SC-003**: Tras cualquier reproducción, el recuento y la suma de comprobación de todas las
  tablas de datos reales son idénticos a los de antes (0 diferencias).
- **SC-004**: El 100 % de los eventos reproducidos conserva su tiempo de ocurrencia original;
  ninguno se desplaza.
- **SC-005**: Los cinco casos sintéticos terminan exactamente como se espera (5 de 5).
- **SC-006**: Tras reiniciar el consumidor a mitad de la reproducción, el resultado final es
  idéntico al de una ejecución sin reinicio.
- **SC-007**: Repetir tras el reinicio del espacio de reproducción produce un resultado idéntico
  al de la primera ejecución y no modifica los datos reales.
- **SC-008**: Pausar detiene las publicaciones en menos de 2 segundos y reanudar continúa sin
  saltos ni repeticiones.

## Assumptions

- El catálogo de `data/usgs/catalog/` y su registro de la spec 003 están disponibles localmente;
  no se vuelve a consultar a USGS ni se versionan datos.
- El modelo de las specs 002 a 004 ya ofrece esquema `replay`, `replay.reset()`, propósito
  `replay_selection` y la regla de `replayed_at`; no se cambia salvo necesidad demostrada y
  justificada en el plan.
- El instante de reproducción lo añade quien reproduce; el plan decidirá si coincide con el que
  hoy asigna el consumidor al leer del topic de reproducción.
- «Zona» se interpreta con el país asignado por la spec 004 y/o un recuadro geográfico; el plan
  fijará cuál.
- La demostración se ejecuta en un único equipo con Compose; el control (pausar, reanudar,
  detener) es por línea de órdenes, sin interfaz gráfica.
- Los casos sintéticos son un conjunto fijo y pequeño versionado en Git (como lote mínimo de
  prueba); el histórico reproducido sale de `data/`.
- Fuera de alcance: contrato de la API y etiquetado «REPRODUCCIÓN» (006), panel (007) y análisis
  y conclusiones (008).
