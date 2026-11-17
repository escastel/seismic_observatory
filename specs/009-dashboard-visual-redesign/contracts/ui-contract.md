# Contrato de interfaz del panel rediseñado (009)

No hay contrato HTTP nuevo: el panel sigue consumiendo solo `specs/006-query-api/contracts/api.md`. Este documento fija lo que la **interfaz** debe cumplir; es el criterio de revisión
de las pruebas de lógica pura y de las comprobaciones en navegador.

## 1. Tema
- Oscuro por defecto; claro cuando el dispositivo lo pide (`prefers-color-scheme: light`); cambia sin recargar y sin perder la lectura.
- Tokens mínimos (ambos temas): fondo, superficie, borde, texto, texto secundario, acento, éxito, aviso, error, foco; profundidad (3 colores + ND). Contraste de texto ≥ 4,5:1 y de elementos gráficos ≥ 3:1 en ambos temas.
- `color-scheme` declarado; `meta theme-color` por tema.

## 2. Mapa
- Selector de fondo (radio accesible): **Simple**, **Relieve**, **Satélite**. Por defecto Simple. `Simple` y `Relieve` tienen variante clara y oscura según el tema; `Satélite` es único.
- Capas opcionales (casillas, independientes del fondo): **Mapa de calor**, **Agrupar eventos**, **Límites de placas**. Los círculos por magnitud y profundidad son la capa base de eventos y se sustituyen por grupos cuando «Agrupar» está activo.
- Al elegir **Relieve** se ofrece «Límites de placas» activada por defecto (el usuario puede quitarla); en los demás fondos está desactivada.
- Rótulo de muestra, visible junto al selector: «Muestra: N de TOTAL» si `N < TOTAL`, «Todos los eventos del periodo» si `N = TOTAL`; aplica a calor y agrupación.
- Atribución visible del fondo y de las capas activas (texto de `research.md` R2 y R3). Pie de página con las atribuciones y la nota de que los proveedores de teselas ven la IP y el `Referer`.
- Fallo de teselas o de capa: aviso en una región `role="status"` y vuelta a Simple; los eventos no se pierden.
- Leyenda: profundidad (color), tamaño (magnitud), ND (borde discontinuo) y, si procede, calor y límites de placas; legible en ambos temas.
- Los círculos mantienen: tamaño por magnitud, color por profundidad, borde discontinuo para ND. La información no depende solo del color.

## 3. Tarjetas de resumen
Cinco tarjetas en la cabecera: **Eventos** (total de la API), **Última ingesta** (UTC), **Estado** (al día, desactualizado o backend inaccesible), **Periodo** (UTC, inicio inclusivo y fin exclusivo) y **Sin valor** (magnitud y profundidad por separado). Cada una con su unidad y filtros aplicados;
`ND` cuando no hay dato; «REPRODUCCIÓN» si procede. Las cifras salen de `Statistics` y del estado del sistema, nunca de la muestra del mapa. Sin «magnitud máxima».

## 4. Gráficos
- Cuatro: eventos por hora UTC, por país, distribución de magnitud y distribución de profundidad (Chart.js).
- Cada uno: título, unidad, periodo, filtros, registros sin valor, leyenda si hay más de una serie, colores del tema y `role="img"` con descripción.
- Cada uno con su tabla equivalente en «Ver tabla de datos» (`<details>`), completa y operable con teclado.
- «Sin país asignado» aparece como una fila más del gráfico por país. La etiqueta «REPRODUCCIÓN» se muestra en el encabezado del gráfico en modo reproducción.
- Colores de profundidad iguales a los del mapa.

## 5. Ficha del evento
- Se abre desde un círculo, un grupo (lista de eventos) o el botón «Ver ficha» de una fila de la tabla. Diálogo (`role="dialog"`, `aria-modal`, título), foco inicial en el cierre, retorno del foco al origen, cierre con Escape y botón.
- Contenido: id, magnitud y tipo, profundidad, lugar, hora UTC, país («Sin país asignado» si no hay), continente, subregión; en reproducción, hora de reproducción y «Sintético». `ND` donde falte el valor.
- Todo el texto de la ficha es texto (sin HTML).
- Panel lateral en escritorio y hoja inferior en pantallas estrechas.

## 6. Movimiento
Las transiciones y animaciones (apertura de la ficha, cambio de capa, gráficos, tarjetas) solo se aplican con `prefers-reduced-motion: no-preference`; con `reduce` no hay movimiento.

## 7. Identidad
Nombre «seismicobservatory» en la cabecera y en `<title>`; logotipo SVG «S» con onda sísmica (propuesta: `references/logo-proposal.svg`), favicon, `currentColor` para adaptarse al tema; tipografía del sistema.

## 8. Lo que no cambia
Periodo, filtros, unidad y sin valor visibles; mismos filtros en mapa, tabla y estadísticas; refresco de 60 s sin solapes; avisos de datos desactualizados y de backend inaccesible con la última lectura; modo «REPRODUCCIÓN»; tabla alternativa al mapa y al color;
accesibilidad (teclado, regiones `aria-live`, axe-core sin violaciones en ambos temas); nunca consulta USGS; solo la API de la 006.

## 9. Rendimiento y red
- Carga diferida de Chart.js, markercluster, leaflet.heat, límites de placas y teselas de relieve o satélite hasta que se eligen.
- Ninguna petición de teselas o de placas pasa por el túnel de ngrok; las peticiones al túnel siguen siendo solo las de la API (eventos, estadísticas, salud).
