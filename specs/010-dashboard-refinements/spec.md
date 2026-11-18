# Feature Specification: Ajustes de diseño, distribución y filtrado del panel

**Feature Branch**: `010-dashboard-refinements`

**Created**: 2026-11-18

**Status**: Draft

**Input**: User description: "Spec 010: ajustes de diseño, distribución y filtrado del panel rediseñado en la 009, a petición de la usuaria, sin cambiar el contrato de la API de consulta (006). Panel más limpio e intuitivo, con el mapa visible nada más entrar, cabecera, avisos, estado y filtros más compactos y un arreglo del filtrado cuando un país no tiene eventos."

**Depende de**: `specs/009-dashboard-visual-redesign` (panel rediseñado, integrado en `main`, PR #10), `specs/007-angular-dashboard` y
`specs/006-query-api` (contrato HTTP, fuente de verdad: no se modifica). Parte de `main`.

**Trazabilidad**: constitución principios VI, VII y VIII; enunciado §8 (puntos 1 a 7), §9 y pruebas 9 y 10 de §11.

**Referencia visual aprobada**: [references/mockup/](references/mockup/index.html) (capturas en oscuro, claro, móvil, con detalles abiertos y con el aviso de
«sin eventos») y los comentarios de la usuaria en [references/](references/) (calor actual, idea de calor y agrupación actual). Le gustan el estilo, el diseño y el color del mockup.

**Naturaleza**: presentación del panel más **una corrección de la API** (`GET /api/estadisticas` incumple su propio contrato cuando ningún evento cumple el filtro). No añade datos ni
métricas y no cambia lo que el enunciado exige del panel.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - El mapa primero y una página más compacta (Priority: P1)

Al abrir el panel se ve, de arriba abajo, la cabecera con el logotipo y el nombre, una zona de avisos, una barra de estado, los filtros en una sola línea con su título y el
mapa con su selector de capas y su leyenda; después, el análisis y la tabla. En móvil el mapa también asoma sin tener que desplazarse mucho.

**Why this priority**: es el cambio de distribución que la usuaria pidió con más claridad («que nada más entrar veas el mapa») y condiciona el resto.

**Independent Test**: abrir el panel en escritorio y en móvil y comprobar el orden, que el mapa queda a la vista y que el estado, los filtros y los avisos siguen siendo legibles y operables.

**Acceptance Scenarios**:

1. **Given** el panel abierto en escritorio, **When** carga, **Then** el título «Seismic Observatory» (con «Seismic» en el color del logotipo y «Observatory» en blanco en el tema oscuro, en texto oscuro en el claro), la barra de estado, los filtros y una parte sustancial del mapa caben en la primera pantalla; no aparecen «BIG DATA · PROYECTO DE AULA» ni «Este panel nunca consulta USGS».
2. **Given** el panel abierto en móvil, **When** carga, **Then** se ven la cabecera, tres métricas de la barra de estado, el botón «Filtros» con sus chips y el comienzo del mapa.
3. **Given** la barra de estado, **When** se pulsa «Detalles», **Then** se despliegan la última lectura correcta del panel, la generación de la respuesta, la última ingesta y los eventos en cuarentena, distinguidos entre sí.
4. **Given** los filtros, **When** se muestran en escritorio, **Then** modo, desde, hasta, magnitud mínima, país y los botones Aplicar y Restablecer van en una sola línea (se reordenan si no caben), con el título «Filtros» y una fila de chips con los filtros aplicados.

---

### User Story 2 - Avisos independientes y reconocibles (Priority: P1)

Los avisos del sistema aparecen arriba, por encima de la barra de estado, cada uno por separado y con un color y un icono según su tipo: error (rojo), aviso (naranja intenso),
información (el color de la marca, ámbar) y éxito (verde).

**Why this priority**: hoy los avisos se mezclan con el panel de estado; separarlos y distinguirlos por gravedad hace el panel más intuitivo y es la parte que más ayuda en las pruebas del túnel.

**Independent Test**: provocar cada situación (backend inaccesible, datos desactualizados, base no disponible, respuesta truncada, periodo demasiado largo, fallo de un fondo o capa, reproducción activa, sin eventos para un filtro, recuperación) y comprobar el tipo, el color, el icono, el texto y el rol anunciado.

**Acceptance Scenarios**:

1. **Given** el backend inaccesible, **When** falla el refresco, **Then** aparece un aviso de **error** (rojo) encima de la barra de estado que conserva e identifica la última lectura.
2. **Given** datos desactualizados o una respuesta truncada, **When** se detecta, **Then** aparece un aviso de **aviso** (naranja intenso) con su texto.
3. **Given** el modo «REPRODUCCIÓN», **When** está activo, **Then** aparece un aviso de **información** (ámbar) que lo indica, además de la etiqueta en el resto de zonas.
4. **Given** que el backend vuelve tras un fallo, **When** se recupera, **Then** aparece un aviso de **éxito** (verde) y desaparece solo.
5. **Given** cualquier aviso, **When** lo lee un lector de pantalla, **Then** se anuncia con el rol adecuado a su gravedad y su significado no depende solo del color (icono y texto).

---

### User Story 3 - Filtrar por un país sin eventos (Priority: P1)

Al filtrar por un país que no tiene eventos en el periodo (por ejemplo Albania), el mapa y la tabla quedan vacíos y aparece un aviso claro, en lugar de seguir mostrando todos los
eventos del mundo.

**Why this priority**: es un fallo real encontrado por la usuaria: el panel muestra datos que no corresponden al filtro, lo que contradice que mapa, tabla y estadísticas apliquen los mismos filtros (principio VII).

**Independent Test**: con el sistema real, filtrar por Albania en las últimas 24 h y comprobar que mapa y tabla quedan vacíos, el total es 0, las estadísticas se muestran y aparece el aviso; probar también un país con eventos.

**Acceptance Scenarios**:

1. **Given** un filtro de país sin eventos en el periodo, **When** se aplica, **Then** el mapa y la tabla quedan vacíos, la barra de estado muestra total 0 y aparece el aviso «No hay eventos sísmicos ahora mismo en <país>» sugiriendo ampliar el periodo.
2. **Given** el mismo filtro, **When** se consultan las estadísticas de la API, **Then** el periodo devuelto tiene inicio y fin numéricos (el fin es «ahora» si no hay eventos), igual que cuando sí hay eventos.
3. **Given** que los eventos llegan bien pero las estadísticas fallan por cualquier otro motivo, **When** ocurre, **Then** el panel muestra los eventos de **ese** filtro, señala el fallo de las estadísticas y no conserva la lectura de otro filtro.
4. **Given** un país con eventos, **When** se filtra, **Then** el comportamiento es el de siempre (mapa, tabla y estadísticas coinciden).

---

### User Story 4 - Mapa más visual: fondos, calor y agrupación (Priority: P2)

El mapa ofrece solo dos fondos, Simple y Satélite; las placas tectónicas son una capa opcional sobre cualquiera, activada por defecto; el mapa de calor tiene un degradado
de amarillo a rojo oscuro bien visible con su leyenda; la agrupación son burbujas con color y tamaño según el número de eventos, con anillo y cifra, y los eventos sueltos conservan su color por profundidad con el mismo brillo.

**Why this priority**: mejora lo que ya existía y que la usuaria encontró poco visual, pero el mapa ya cumple lo exigido sin ello.

**Independent Test**: activar cada capa sobre cada fondo en ambos temas con un periodo largo (más de 1.000 eventos) y otro corto, y comprobar legibilidad, leyendas y rótulo de muestra.

**Acceptance Scenarios**:

1. **Given** el selector de fondo, **When** se abre, **Then** solo ofrece Simple y Satélite; el fondo «Relieve», su código, su atribución y su mención del pie de página ya no existen.
2. **Given** cualquiera de los dos fondos, **When** se carga el panel, **Then** los límites de placas están activados por defecto y pueden quitarse.
3. **Given** el mapa de calor activado, **When** se muestra, **Then** el degradado es claramente visible sobre ambos fondos y ambos temas, con leyenda de colores, y se rotula «densidad de eventos de la muestra» con «N de TOTAL», nunca como peligrosidad ni riesgo.
4. **Given** la agrupación activada, **When** se muestra, **Then** cada grupo es una burbuja con color y tamaño según su recuento, con anillo y cifra, los eventos sueltos usan su color por profundidad con el mismo brillo y el rótulo «N de TOTAL» sigue visible.

---

### User Story 5 - Interruptor de tema (Priority: P2)

Un botón flotante con un sol y una luna permite pasar entre el tema oscuro y el claro. Por defecto el panel sigue el dispositivo (oscuro si no hay preferencia); al pulsar el botón, la
elección manual manda y se recuerda en el navegador.

**Why this priority**: es una comodidad que la usuaria pidió expresamente; el tema ya se adapta al dispositivo sin él.

**Independent Test**: pulsar el botón en ambos sentidos, recargar y comprobar que la elección se conserva; probar con el almacenamiento bloqueado; operarlo con teclado y con lector de pantalla.

**Acceptance Scenarios**:

1. **Given** el panel en el tema del dispositivo, **When** se pulsa el botón, **Then** cambia al otro tema sin recargar y sin perder la lectura.
2. **Given** una elección manual, **When** se recarga el panel, **Then** se mantiene aunque el dispositivo prefiera el otro tema.
3. **Given** un navegador que no permite guardar la elección, **When** se pulsa el botón, **Then** el tema cambia igualmente y el panel no falla.
4. **Given** el botón, **When** se opera con teclado o lector de pantalla, **Then** tiene nombre, indica el tema actual y es alcanzable; con «reducir movimiento» no hay animación.

---

### User Story 6 - Nada de lo verificado se pierde (Priority: P1)

El rediseño no rompe lo que la 007 y la 009 ya demostraron: periodo, filtros, unidad y sin valor visibles, ND, «Sin país asignado», etiqueta «REPRODUCCIÓN», refresco cada 60 s sin solapes, avisos de desactualizado y de backend inaccesible conservando la última lectura, tabla como alternativa, ficha del evento, accesibilidad y que las teselas y placas no pasen por el túnel.

**Why this priority**: el panel sigue siendo parte de la entrega evaluada (§8, §9 y las pruebas 9 y 10 de §11).

**Independent Test**: repetir los escenarios de la 007 y la 009 y las pruebas de cerrar y reabrir el túnel sobre el panel nuevo; los resultados deben ser los mismos.

**Acceptance Scenarios**:

1. **Given** el panel nuevo, **When** se repiten los escenarios de la 007 y la 009, **Then** todos dan el mismo resultado esperado.
2. **Given** ambos temas, **When** se ejecuta la comprobación automática de accesibilidad, **Then** no hay violaciones y todo es operable con teclado.
3. **Given** el túnel cerrado y reabierto, **When** pasa el siguiente refresco, **Then** el panel avisa conservando la última lectura y se recupera solo.

---

### Edge Cases

- Filtro por un país sin eventos con un periodo cerrado (inicio y fin dados) y con el periodo por defecto.
- Filtro sin eventos junto con un mínimo de magnitud muy alto.
- Fallan a la vez los eventos y las estadísticas (se mantiene el aviso de backend inaccesible con la última lectura).
- Varios avisos a la vez (se apilan por gravedad: error, aviso, información, éxito) y un aviso de éxito que caduca.
- Pantalla muy estrecha o texto agrandado: la barra de estado, los filtros y el mapa no desbordan.
- Más de 1.000 eventos: calor y agrupación etiquetados como muestra.
- Un fondo o capa no carga: aviso y vuelta al fondo Simple sin perder eventos.
- La elección manual de tema guardada y el dispositivo cambia de preferencia después.
- El almacenamiento del navegador no está disponible.
- Modo «REPRODUCCIÓN» con filtro sin eventos.

## Requirements *(mandatory)*

### Functional Requirements

**Cabecera y distribución**

- **FR-001**: La cabecera MUST mostrar el logotipo y el nombre «Seismic Observatory» con «Seismic» en el color del logotipo y «Observatory» en blanco en el tema oscuro (texto oscuro y color del logotipo con contraste suficiente en el claro), y MUST NOT mostrar «BIG DATA · PROYECTO DE AULA» ni «Este panel nunca consulta USGS».
- **FR-002**: El orden de la página MUST ser, de arriba abajo: cabecera, zona de avisos, barra de estado, filtros, mapa (con selector de capas y leyenda), análisis y tabla de eventos; el mapa MUST asomar en la primera pantalla en escritorio y en móvil.

**Avisos**

- **FR-003**: Los avisos MUST mostrarse arriba, por encima de la barra de estado, cada uno independiente, con su tipo: error (rojo), aviso (naranja intenso), información (color de la marca, ámbar) y éxito (verde).
- **FR-004**: Cada aviso MUST llevar icono y texto además del color, y MUST anunciarse a lectores de pantalla con el rol adecuado a su gravedad.
- **FR-005**: Los avisos MUST cubrir al menos: datos desactualizados, backend inaccesible, base no disponible, respuesta truncada, periodo demasiado largo, fallo de un fondo o capa, modo reproducción activo, ausencia de eventos para un filtro y recuperación del backend.
- **FR-006**: Los avisos de error y de datos desactualizados MUST conservar e identificar la última lectura correcta, como hasta ahora.

**Estado y resumen**

- **FR-007**: Una única barra de estado MUST sustituir al panel «Estado del panel» y a las cinco tarjetas de resumen, mostrando Eventos, Última ingesta, Estado, Periodo (UTC) y Sin valor (magnitud y profundidad) con las mismas cifras de la API, su periodo, filtros y unidad.
- **FR-008**: «Detalles» MUST desplegar, distinguidas, la última lectura correcta del panel, la generación de la respuesta, la última ingesta y los eventos en cuarentena.
- **FR-009**: En pantallas estrechas la barra MUST mostrar tres métricas y dejar el resto en «Detalles».
- **FR-010**: Toda cifra de la barra MUST salir de la API (no de la muestra del mapa) y MUST mostrar ND cuando no haya dato.

**Filtros**

- **FR-011**: Los filtros MUST ir en una sola línea cuando caben (modo, desde, hasta, magnitud mínima, país, Aplicar y Restablecer), con el título «Filtros», y una fila de chips con los filtros aplicados.
- **FR-012**: En pantallas estrechas MUST haber un botón «Filtros» que los despliega, con los chips visibles.
- **FR-013**: Los filtros MUST seguir aplicándose igual al mapa, la tabla y las estadísticas.

**Mapa**

- **FR-014**: El selector de fondo MUST ofrecer solo Simple (variante clara u oscura según el tema) y Satélite; el fondo Relieve, su código, su atribución y su mención en el pie de página MUST eliminarse.
- **FR-015**: Los límites de placas MUST ser una capa opcional sobre cualquiera de los dos fondos, activada por defecto.
- **FR-016**: El mapa de calor MUST ser una capa opcional con un degradado de amarillo a rojo oscuro claramente visible en ambos temas y fondos, con leyenda de colores, y MUST rotularse como «densidad de eventos de la muestra» con «N de TOTAL»; MUST NOT presentarse como peligrosidad, predicción ni riesgo.
- **FR-017**: La agrupación MUST mostrarse como burbujas con color y tamaño según el número de eventos, anillo y cifra; los eventos sueltos MUST conservar su color por profundidad con el mismo brillo; el rótulo «N de TOTAL» MUST seguir visible.
- **FR-018**: Las leyendas del mapa MUST mantenerse como en el mockup aprobado (profundidad, tamaño, ND, agrupación y calor).
- **FR-019**: Gráficos y tabla de eventos MUST mantenerse como en la 009.

**Tema**

- **FR-020**: MUST haber un botón flotante con un sol y una luna para alternar entre oscuro y claro; por defecto el tema sigue el dispositivo (oscuro si no hay preferencia) y la elección manual prevalece y se recuerda en el navegador.
- **FR-021**: El botón MUST ser accesible (nombre, estado del tema, teclado), MUST funcionar aunque el almacenamiento del navegador falle y MUST respetar «reducir movimiento».

**Filtrado sin eventos (corrección)**

- **FR-022**: Al filtrar por un país sin eventos en el periodo, el mapa y la tabla MUST quedar vacíos, el total MUST ser 0 y MUST aparecer un aviso «No hay eventos sísmicos ahora mismo en <país>» que sugiera ampliar el periodo; el panel MUST NOT seguir mostrando eventos de otro filtro.
- **FR-023**: `GET /api/estadisticas` MUST devolver siempre un periodo con inicio y fin numéricos, como exige el contrato de la 006; cuando ningún evento cumple el filtro y no se dio fin, el fin MUST ser el instante actual. Es una corrección que hace cumplir el contrato, no un cambio del contrato.
- **FR-024**: Si los eventos llegan bien y solo falla la respuesta de estadísticas, el panel MUST mostrar los eventos de ese filtro, señalar el fallo de las estadísticas y MUST NOT conservar la lectura de otro filtro.

**No se pierde**

- **FR-025**: El panel MUST seguir mostrando periodo, filtros, unidad y registros sin valor; ND; «Sin país asignado»; la etiqueta «REPRODUCCIÓN» en estado, mapa, tabla y gráficos; refresco cada 60 s sin solapes; la tabla como alternativa al mapa y al color; la ficha del evento; y texto de usuario siempre como texto.
- **FR-026**: El panel MUST seguir consultando solo la API de la 006 con su contrato actual y MUST NOT consultar USGS; las teselas y las placas MUST NOT pasar por el túnel.
- **FR-027**: El panel MUST seguir siendo accesible en ambos temas: operable con teclado, regiones de estado anunciadas y sin violaciones en la comprobación automática de accesibilidad.

**Restricciones**

- **FR-028**: MUST NOT modificarse el contrato de la API ni el modelo de datos; la lógica de datos de la 007 solo se toca para la tolerancia a fallos de las estadísticas (FR-024), documentado.
- **FR-029**: La corrección de la API MUST tener una prueba de comportamiento, y el panel MUST comprobarse en navegador real en ambos temas, escritorio y móvil, con evidencia de esperado y observado en `docs/evidence/010/`, incluido el caso del país sin eventos con el sistema real.

### Key Entities

- **Aviso**: tipo (error, aviso, información, éxito), icono, texto, gravedad y rol anunciado; puede ser persistente o caducar.
- **Barra de estado**: Eventos, Última ingesta, Estado, Periodo y Sin valor, más los detalles desplegables (última lectura del panel, generación, ingesta, cuarentena).
- **Filtros aplicados**: conjunto de filtros mostrado como título «Filtros» y chips.
- **Fondo de mapa**: Simple (claro u oscuro) o Satélite, con su atribución.
- **Capa**: límites de placas (por defecto activa), mapa de calor y agrupación, con su leyenda y su rótulo de muestra.
- **Preferencia de tema**: la del dispositivo o la elegida manualmente con el botón.
- **Lectura de un filtro**: eventos y estadísticas que corresponden al mismo filtro; nunca se mezcla con la de otro.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Con el panel abierto en escritorio (1440 × 900) caben en la primera pantalla la cabecera, la barra de estado, los filtros y al menos el 50 % de la altura del mapa; en móvil (390 × 844) asoma el mapa en la primera pantalla.
- **SC-002**: El 100 % de los avisos de la lista de FR-005 aparece como un bloque independiente sobre la barra de estado, con tipo, color, icono, texto y rol correctos.
- **SC-003**: Al filtrar por un país sin eventos con el sistema real, el 100 % de las veces el mapa y la tabla quedan vacíos, el total es 0 y aparece el aviso; 0 veces se muestran eventos de otro filtro.
- **SC-004**: La API devuelve inicio y fin numéricos en el periodo de las estadísticas en el 100 % de las consultas, con y sin eventos.
- **SC-005**: Los dos fondos, las tres capas y el interruptor de tema funcionan en ambos temas; las capas de muestra llevan siempre su «N de TOTAL».
- **SC-006**: El interruptor de tema conserva la elección tras recargar y funciona con el almacenamiento bloqueado; la comprobación automática de accesibilidad da 0 violaciones en ambos temas.
- **SC-007**: El 100 % de los escenarios de la 007 y la 009 y de las pruebas de cerrar y reabrir el túnel dan el mismo resultado esperado.
- **SC-008**: Existen capturas en tema claro y oscuro, escritorio y móvil, de cada tipo de aviso y del caso del país sin eventos, y una comprobación con el sitio de Netlify y el túnel, todas en `docs/evidence/010/`.
- **SC-009**: Una persona nueva identifica el estado del sistema y el mapa en menos de 10 segundos desde la primera pantalla.

## Assumptions

- La usuaria ha aprobado el mockup, los colores de los avisos (rojo, naranja intenso, ámbar de la marca y verde), el orden de la página y las decisiones del mapa; no quedan dependencias suyas.
- El mockup es una referencia de estilo y distribución, no un diseño píxel a píxel; los detalles finos se ajustan en la implementación con capturas.
- «Naranja intenso» para los avisos y «ámbar» para la información se distinguen además por su icono y texto; los tonos exactos se eligen en el plan garantizando contraste en ambos temas.
- La elección manual de tema se guarda solo en el navegador de la persona (comodidad individual), con tolerancia a que no esté disponible.
- Los avisos de éxito caducan solos; los de error y aviso permanecen mientras persista la causa.
- El fallo encontrado en `api/app/stats.py` (periodo con fin nulo si no hay eventos) es un incumplimiento del contrato de la 006 y su corrección se documenta como cambio justificado (FR-028); no cambia ningún otro comportamiento de la API.
- Gráficos y tabla de eventos no se rediseñan (se mantienen como en la 009) y la lógica de datos de la 007 no cambia salvo la tolerancia a fallos de estadísticas.
- Fuera de alcance: cambios en el contrato de la API, el modelo de datos o nuevos datos y métricas; mapa 3D; regiones oceánicas en la API o el panel; cuentas o autenticación; servicios cloud nuevos.
- La comprobación con el sitio de Netlify y el túnel se hace tras el merge a `main` (Netlify despliega al integrar), como en la 009.
- Orquestación según `CLAUDE.md`: la sesión principal hace integración, navegador real, API, evidencias y memoria; agentes Sonnet para componentes y pruebas; Haiku para documentación; nunca dos ejecuciones de `tests/db` a la vez.
