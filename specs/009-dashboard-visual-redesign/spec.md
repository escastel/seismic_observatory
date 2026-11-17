# Feature Specification: Rediseño visual y personalización del panel

**Feature Branch**: `009-dashboard-visual-redesign`

**Created**: 2026-11-17

**Status**: Draft

**Input**: User description: "Spec 009: rediseño visual y personalización del panel Angular (007), con permiso del profesor, sobre la API de consulta (006) sin modificar su contrato. El panel debe ser más visual y tener identidad propia sin perder nada de lo ya verificado: tema claro u oscuro según el dispositivo, varios mapas base y capas, gráficos más visuales, tarjetas de resumen y una ficha de evento más rica."

**Depende de**: `specs/007-angular-dashboard` (panel actual, ya verificado), `specs/006-query-api` (contrato HTTP, fuente de
verdad: no se modifica) y `specs/008-analysis-costs-deliverables` (rama de partida). La 007 y la 008 todavía no están integradas en `main`.

**Trazabilidad**: constitución principios VI, VII y VIII; enunciado §8 (puntos 1 a 7), §9 y pruebas 9 y 10 de §11. El profesor ha
permitido personalizar el panel; esa permisión es la que justifica esta spec.

**Naturaleza**: es una funcionalidad de **presentación**. No añade datos, no cambia la API, el modelo ni el contrato, y no cambia lo que el
enunciado exige del panel. Lo que ya está demostrado en la 007 (`docs/evidence/007/`) debe seguir cumpliéndose.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tema claro u oscuro y mapas base (Priority: P1)

Quien abre el panel lo ve en el tema claro u oscuro que usa su dispositivo, sin pulsar nada, y puede elegir el mapa base: el simple de siempre
(que cambia con el tema), un relieve con las placas tectónicas o el satélite. Sobre cualquiera puede activar un mapa de calor de densidad y la
agrupación de eventos, además de los círculos por magnitud y profundidad.

**Why this priority**: es el cambio más visible y el que la usuaria pidió con más detalle; el mapa es el elemento central del panel.

**Independent Test**: abrir el panel con el dispositivo en modo claro y en modo oscuro y recorrer los cuatro mapas y las dos capas; en todos los
casos los eventos siguen siendo legibles, los filtros se aplican igual y los datos mostrados no cambian.

**Acceptance Scenarios**:

1. **Given** un dispositivo en modo oscuro, **When** se abre el panel, **Then** el panel, el mapa simple, los gráficos y las tarjetas usan el tema oscuro; al cambiar el dispositivo a claro, el panel pasa al tema claro sin recargar.
2. **Given** el panel abierto, **When** se elige el mapa de relieve con placas tectónicas o el satélite, **Then** el fondo cambia, los eventos siguen visibles con su color y tamaño, y la atribución de la fuente del fondo se muestra.
3. **Given** un periodo con más eventos de los que el mapa dibuja, **When** se activa el mapa de calor o la agrupación, **Then** la capa indica que se calcula sobre una muestra («N de TOTAL») y no la presenta como la densidad del conjunto completo.
4. **Given** una capa o un fondo que no se puede cargar, **When** falla la carga de sus teselas o datos, **Then** el panel sigue funcionando con el mapa simple y lo avisa, sin perder los eventos.

---

### User Story 2 - Gráficos y tarjetas de resumen (Priority: P1)

Las estadísticas se muestran con gráficos de verdad (eventos por hora UTC, por país, distribución de magnitud y de profundidad), con color y leyenda, y
con la tabla de datos como alternativa accesible. Arriba, tarjetas de resumen con cifras grandes: total de eventos, última ingesta, estado del sistema,
periodo consultado y registros sin valor.

**Why this priority**: convierte el análisis del panel en algo comprensible a primera vista, que es lo que se busca con «más visual».

**Independent Test**: con unos filtros dados, comparar cada cifra de las tarjetas y de los gráficos con la respuesta de la API para los mismos filtros; deben coincidir, y cada gráfico debe tener su tabla.

**Acceptance Scenarios**:

1. **Given** un periodo y unos filtros, **When** se muestran las tarjetas, **Then** cada cifra es la que devuelve la API de estadísticas, con su periodo, filtros y unidad, y los registros sin valor figuran aparte.
2. **Given** un gráfico, **When** se consulta, **Then** tiene título, unidad, leyenda, tema adaptado y una tabla de datos equivalente accesible con teclado y lector de pantalla.
3. **Given** el modo «REPRODUCCIÓN», **When** se muestran tarjetas y gráficos, **Then** todos llevan la etiqueta «REPRODUCCIÓN».
4. **Given** una media histórica de cero o una magnitud o profundidad sin valor, **When** se muestran, **Then** aparece «ND» y no un cero ni una razón infinita.

---

### User Story 3 - Ficha del evento y animaciones (Priority: P2)

Al pulsar un evento (en el mapa o en la tabla) se abre una ficha más rica: magnitud con su tipo, profundidad, lugar, hora UTC, país, continente y subregión,
y si faltan valores se muestran como ND. Las transiciones son suaves y se desactivan cuando el dispositivo pide menos movimiento.

**Why this priority**: mejora la experiencia, pero el panel ya muestra esa información; es refinamiento, no capacidad nueva.

**Independent Test**: pulsar un evento con todos los datos y otro con valores nulos y comprobar la ficha; activar «reducir movimiento» en el dispositivo y comprobar que no hay animaciones.

**Acceptance Scenarios**:

1. **Given** un evento, **When** se pulsa, **Then** la ficha muestra sus datos con unidades y la hora en UTC, sin interpretar el texto del lugar como código.
2. **Given** un evento sin país, **When** se abre la ficha, **Then** dice «Sin país asignado» y el evento sigue en el análisis.
3. **Given** un dispositivo con «reducir movimiento», **When** se abre y se cierra una ficha o se cambia de capa, **Then** no hay animaciones de movimiento.

---

### User Story 4 - Identidad propia (Priority: P2)

El panel tiene nombre, logotipo, paleta y tipografía propios del proyecto, coherentes en los dos temas y en móvil.

**Why this priority**: personaliza el panel, pero depende de que la usuaria apruebe o aporte nombre y logotipo; el resto funciona sin él.

**Independent Test**: revisar el panel en ambos temas, en escritorio y móvil, y comprobar que nombre, logotipo y paleta son los aprobados y que el contraste es suficiente.

**Acceptance Scenarios**:

1. **Given** el nombre y el logotipo aprobados por la usuaria, **When** se abre el panel, **Then** aparecen en la cabecera y en el título de la pestaña, en ambos temas.
2. **Given** los colores de profundidad y los de la paleta, **When** se muestran en tema claro y oscuro, **Then** cumplen el contraste mínimo de accesibilidad y la información no depende solo del color (forma, tamaño y tabla).

---

### User Story 5 - Nada de lo verificado se pierde (Priority: P1)

El rediseño no rompe nada de lo que la 007 ya demostró: filtros coherentes entre mapa, tabla y estadísticas, avisos de datos desactualizados y de backend inaccesible conservando la última lectura, refresco cada 60 s sin solapes, «Sin país asignado», nulos como ND, etiqueta «REPRODUCCIÓN» y accesibilidad.

**Why this priority**: el panel sigue siendo parte de la entrega evaluada (§8, §9 y las pruebas 9 y 10 de §11); un rediseño que las rompa es peor que no rediseñar.

**Independent Test**: repetir los escenarios V1 a V15 de la 007 y las pruebas de cierre y reapertura del túnel sobre el panel rediseñado; los resultados deben ser los mismos.

**Acceptance Scenarios**:

1. **Given** el panel rediseñado, **When** se repiten los escenarios de la 007, **Then** todos dan el mismo resultado esperado.
2. **Given** el túnel cerrado, **When** llega el siguiente refresco, **Then** el panel avisa del fallo conservando la última lectura identificada como tal; al reabrir, se recupera solo en un refresco.
3. **Given** ambos temas, **When** se ejecuta la comprobación automática de accesibilidad, **Then** no hay violaciones y todo es operable con teclado.

---

### Edge Cases

- El dispositivo cambia de modo claro a oscuro con el panel abierto (se adapta sin recargar ni perder la lectura).
- Las teselas del mapa base, del satélite o los límites de placas no cargan (se avisa y se vuelve al mapa simple).
- La conexión es móvil y lenta: el panel sigue siendo utilizable y el peso inicial es razonable.
- Más de 1.000 eventos en el periodo: mapa de calor y agrupación etiquetados como muestra.
- Cero eventos, un solo evento o eventos superpuestos en el mismo punto.
- Magnitud o profundidad nulas, o negativas: se conservan y se muestran (ND o valor) en tarjetas, fichas y gráficos.
- El dispositivo pide menos movimiento o alto contraste.
- Pantalla muy estrecha: gráficos, tarjetas y ficha se reorganizan sin desbordar.
- Texto del lugar con marcas o caracteres especiales: siempre se muestra como texto.
- El modo «REPRODUCCIÓN» activo: la etiqueta aparece en todas las zonas nuevas.
- La referencia visual del relieve o el logotipo aún no están: el panel usa el relieve genérico y un identificador provisional.

## Requirements *(mandatory)*

### Functional Requirements

**Tema**

- **FR-001**: El panel MUST adoptar el tema claro u oscuro del dispositivo al abrirse y MUST cambiar de tema sin recargar cuando el dispositivo cambia.
- **FR-002**: Mapa simple, gráficos, tarjetas, fichas y tabla MUST estar diseñados y comprobados en ambos temas, con contraste suficiente.

**Mapa**

- **FR-003**: El panel MUST ofrecer un selector de mapa base con: simple (con variante clara y oscura según el tema), relieve con placas tectónicas y satélite.
- **FR-004**: El panel MUST permitir activar sobre cualquier mapa base un mapa de calor de densidad y la agrupación de eventos, además de los círculos actuales por magnitud y profundidad.
- **FR-005**: El mapa de calor y la agrupación MUST etiquetarse como calculados sobre la muestra («N de TOTAL») cuando el periodo tenga más eventos de los dibujados, y MUST NOT presentarse como densidad del conjunto completo.
- **FR-006**: Cada fondo y capa de terceros MUST mostrar su atribución y cumplir su licencia y política de uso, y MUST NOT pasar por el túnel público de la API.
- **FR-007**: Si un fondo o capa no carga, el panel MUST avisar y conservar el mapa simple con los eventos.
- **FR-008**: Los círculos MUST seguir codificando la magnitud por tamaño y la profundidad por color, con la leyenda y el tratamiento visible de nulos (ND) actuales, y MUST NOT depender solo del color.

**Gráficos y tarjetas**

- **FR-009**: Las estadísticas MUST mostrarse con gráficos para eventos por hora UTC, por país, distribución de magnitud y distribución de profundidad, con título, unidad, leyenda y color adaptado al tema.
- **FR-010**: Cada gráfico MUST tener una tabla de datos equivalente, accesible con teclado y lector de pantalla.
- **FR-011**: La cabecera MUST mostrar tarjetas de resumen con: total de eventos, última ingesta, estado del sistema, periodo consultado y registros sin valor.
- **FR-012**: Toda cifra de tarjetas y gráficos MUST salir de la API de estadísticas con los mismos filtros que el mapa y la tabla, MUST NOT recalcularse a partir de la muestra del mapa y MUST indicar periodo, filtros, unidad y registros sin valor.
- **FR-013**: Una media histórica cero o un valor sin dato MUST mostrarse como «ND», no como cero ni como razón infinita.

**Ficha y animaciones**

- **FR-014**: Pulsar un evento en el mapa o en la tabla MUST abrir una ficha con magnitud y tipo, profundidad, lugar, hora UTC, país, continente y subregión, mostrando ND donde falte el valor y «Sin país asignado» cuando no haya país.
- **FR-015**: Las transiciones MUST ser suaves y MUST desactivarse cuando el dispositivo pida reducir el movimiento.
- **FR-016**: Todo texto de usuario o de la API (lugar, identificadores) MUST mostrarse siempre como texto, nunca como marcado.

**Identidad**

- **FR-017**: El panel MUST mostrar el nombre y el logotipo aprobados por la usuaria en la cabecera y en el título de la pestaña, con una paleta y una tipografía propias coherentes en ambos temas.
- **FR-018**: Mientras el nombre o el logotipo no estén aprobados, el panel MUST usar un identificador provisional que no suplante a ninguna organización ni marca real.

**Lo que no se pierde**

- **FR-019**: El panel MUST seguir mostrando periodo, filtros, unidad y registros sin valor; aplicar los mismos filtros al mapa, la tabla y las estadísticas; y conservar «Sin país asignado», ND, la etiqueta «REPRODUCCIÓN» en estado, mapa, tabla y gráficos, y la tabla consultable como alternativa al mapa y al color.
- **FR-020**: El panel MUST seguir refrescando cada 60 s sin solapes, avisar de datos desactualizados y de backend inaccesible conservando e identificando la última lectura, y recuperarse solo al volver el backend.
- **FR-021**: El panel MUST seguir consultando solo la API de la spec 006 con su contrato actual y MUST NOT consultar USGS.
- **FR-022**: El panel MUST seguir siendo accesible: operable con teclado, regiones de estado anunciadas, y sin violaciones en la comprobación automática de accesibilidad en ambos temas.

**Restricciones**

- **FR-023**: Las bibliotecas nuevas MUST fijarse a versión exacta y solo añadirse si resuelven un requisito de esta spec.
- **FR-024**: MUST NOT modificarse el contrato de la API, el modelo de datos ni la lógica de datos de la 007, salvo necesidad demostrada y documentada como cambio justificado.
- **FR-025**: El peso inicial y el rendimiento en móvil MUST mantenerse en un nivel razonable; los fondos y capas pesados MUST cargarse solo cuando se elijan.
- **FR-026**: MUST comprobarse en navegador real, en ambos temas, escritorio y móvil, con evidencia de resultado esperado y observado en `docs/evidence/009/`, y con una comprobación del sitio de Netlify y del túnel.
- **FR-027**: Las pruebas automáticas MUST comprobar comportamiento de la lógica pura, no la presencia de texto en el código; la documentación MUST estar en español y el código en inglés; no se versionan datos ni secretos.

### Key Entities

- **Tema**: claro u oscuro, tomado del dispositivo; define colores del panel, del mapa simple y de los gráficos.
- **Mapa base**: simple (claro u oscuro), relieve con placas tectónicas o satélite; cada uno con su fuente y su atribución.
- **Capa de eventos**: círculos, mapa de calor o agrupación; cada una con indicación de que se calcula sobre la muestra cuando hay truncado.
- **Tarjeta de resumen**: cifra grande con su etiqueta, periodo, filtros, unidad y registros sin valor, tomada de la API.
- **Gráfico**: representación de una distribución o serie con su leyenda y su tabla de datos equivalente.
- **Ficha de evento**: vista detallada de un evento con valores o ND.
- **Identidad**: nombre, logotipo, paleta y tipografía del proyecto.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de los escenarios de la 007 (V1 a V15) y de las pruebas de cerrar y reabrir el túnel dan el mismo resultado esperado en el panel rediseñado.
- **SC-002**: La comprobación automática de accesibilidad da 0 violaciones en ambos temas y todo el panel es operable solo con teclado.
- **SC-003**: El 100 % de las cifras de tarjetas y gráficos coincide con la API de estadísticas para los mismos filtros, y 0 se calculan sobre la muestra del mapa.
- **SC-004**: Los cuatro mapas base y las dos capas se pueden alternar y todos los eventos siguen siendo legibles en ambos temas; el 100 % de las capas de muestra lleva su etiqueta «N de TOTAL» cuando hay truncado.
- **SC-005**: Cada fondo y capa de terceros muestra su atribución y ninguna petición de fondos o capas pasa por el túnel público de la API.
- **SC-006**: Una persona nueva identifica el estado del sistema, el total de eventos y el periodo en menos de 10 segundos desde la primera pantalla, en escritorio y en móvil.
- **SC-007**: Con una conexión móvil, el panel queda utilizable en menos de 5 segundos tras abrirlo y el peso inicial no crece más de lo que se documente y apruebe en el plan.
- **SC-008**: Con «reducir movimiento» activado no hay animaciones de movimiento; con el modo del dispositivo cambiado, el panel cambia de tema sin recargar y conservando la lectura.
- **SC-009**: Existen capturas en tema claro y oscuro, escritorio y móvil, y una comprobación con el sitio de Netlify y el túnel, todas en `docs/evidence/009/`.

## Assumptions

- La usuaria aportará la referencia visual del relieve con placas tectónicas y aprobará o aportará el nombre y el logotipo; hasta entonces se usa un relieve genérico con límites de placas y un identificador provisional.
- Las fuentes concretas de teselas, satélite y límites de placas se eligen en el plan, comprobando licencia, atribución y política de uso; las de uso gratuito sin clave se prefieren, y ninguna clave va al frontend ni a Git.
- El tema sigue siempre el del dispositivo; no se añade un conmutador manual (puede considerarse más adelante).
- Una cifra de «magnitud máxima» no forma parte de las tarjetas porque la API de estadísticas no la entrega y recalcularla sobre la muestra del mapa está prohibido; si se quisiera, requeriría un cambio justificado del contrato.
- El mapa sigue mostrando como mucho 1.000 eventos por petición; la agrupación y el mapa de calor trabajan sobre esa muestra y así se rotulan.
- Las pruebas de la 007 (Vitest, comprobaciones en navegador, accesibilidad automática) se reutilizan y se amplían; no se rehace la lógica de datos.
- Fuera de alcance: cambios en la API, el modelo o el contrato; nuevos datos o métricas; mapa 3D o globo; regiones oceánicas en la API o el panel (queda para una spec posterior, la 008 hizo la versión solo de análisis en C5); cuentas o autenticación; servicios cloud nuevos.
- Dependencias externas de la usuaria: la referencia del relieve y la aprobación del nombre y logotipo.
- Orquestación según `CLAUDE.md`: la sesión principal hace integración, navegador real, evidencias y memoria; agentes Sonnet para componentes y pruebas; Haiku para documentación; nunca dos ejecuciones de `tests/db` a la vez.
