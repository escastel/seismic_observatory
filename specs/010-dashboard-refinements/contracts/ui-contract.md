# Contrato de interfaz (010)

El contrato HTTP sigue siendo `specs/006-query-api/contracts/api.md`; este documento fija solo la interfaz y la **única precisión de la API** (§0). Hereda el contrato de la 009
(`specs/009-dashboard-visual-redesign/contracts/ui-contract.md`) salvo lo que aquí se sustituye.

## 0. API (corrección que hace cumplir el contrato)
`GET /api/estadisticas` devuelve **siempre** `period.start` y `period.end` como números (ms Unix UTC), con y sin eventos. Con el periodo por defecto en vivo y sin eventos: `start` = ahora − 24 h, `end` = ahora y `hourly.items` con 24 ventanas a cero. Con un periodo dado, los valores dados. En modo
reproducción sin eventos ni inicio: `start = end`, `hourly.items` vacío. Ningún otro campo cambia.

## 1. Orden de la página
Cabecera → zona de avisos → barra de estado → filtros → mapa (selector de capas y leyenda dentro) → análisis → tabla; pie de página con atribuciones. Botón de tema flotante fijo arriba a la derecha (movido desde abajo a petición de la persona autora), por encima de todo salvo la ficha abierta.

## 2. Cabecera
Logotipo + «**Seismic** Observatory» (`Seismic` en el color de acento del logotipo; `Observatory` en blanco en oscuro y en el color de texto en claro). Sin «BIG DATA · PROYECTO DE AULA» ni «Este panel nunca consulta USGS». A la derecha, la insignia «Datos al día»/estado (compacta).

## 3. Zona de avisos
Bloques independientes, uno por aviso, sobre la barra de estado. Tipos, colores, iconos y roles según `research.md` R2:
| Tipo | Color | Icono | Rol |
|---|---|---|---|
| error | rojo | ✕ | `alert` |
| aviso | naranja intenso | ▲ | `status` |
| información | ámbar de la marca | ⓘ | `status` |
| éxito | verde | ✓ | `status`, caduca a los 8 s |
El significado nunca depende solo del color: icono + texto (+ borde). Si no hay avisos, la zona no ocupa espacio. Los avisos de error y de datos desactualizados conservan e identifican la última lectura.

## 4. Barra de estado
Cinco métricas: **Eventos**, **Última ingesta**, **Estado**, **Periodo (UTC)** y **Sin valor** (magnitud · profundidad), con unidad y `ND` sin dato, «REPRODUCCIÓN» si procede. Botón «Detalles» (`aria-expanded`) que despliega: última lectura correcta del panel, generación de la respuesta (API), última ingesta, última
reproducción (solo reproducción), eventos en cuarentena y eventos sin magnitud. ≤ 760 px: solo Eventos, Última ingesta y Estado; el resto en «Detalles». Sin el título «Estado del panel» ni las cinco tarjetas.

## 5. Filtros
Bloque con el título «Filtros». Una sola línea cuando cabe: Modo (Real/Reproducción), Desde (UTC), Hasta (UTC), Magnitud mínima, País, Aplicar, Restablecer (con salto de línea si no cabe). Debajo, chips de los filtros aplicados. ≤ 760 px: botón «Filtros» (`aria-expanded`) que despliega el formulario; los chips siguen visibles. Misma validación y
mismos mensajes de error junto al campo que en la 007.

## 6. Mapa
- Selector de fondo (radio): **Simple** (claro u oscuro con el tema) y **Satélite**. No existe «Relieve».
- Capas (casillas): **Límites de placas** (activada por defecto), **Mapa de calor**, **Agrupar eventos**; independientes del fondo.
- Rótulo de muestra (chip arriba a la izquierda) cuando calor o agrupación están activos: «Muestra: N de TOTAL» o «Todos los eventos del periodo». El calor añade «densidad de eventos de la muestra».
- Calor: degradado amarillo → rojo oscuro, radio y opacidad altos; leyenda de colores («Menos eventos → Más»). No se llama peligrosidad ni riesgo.
- Agrupación: burbujas con cifra, anillo, tamaño (34, 44, 54, 64 px) y color (amarillo, ámbar, naranja rojizo, rojo) por recuento; eventos sueltos con su color de profundidad y halo.
- Leyendas dentro del mapa (profundidad, tamaño, ND, agrupación y calor), plegables en móvil.
- Sin eventos (cualquier filtro, periodo o modo): **aviso emergente** flotante sobre el mapa, no modal, con botón de cierre: título «No hay eventos registrados con las condiciones del filtro», las condiciones aplicadas (país, periodo en UTC, magnitud mínima, modo) y la sugerencia de ampliar el periodo o quitar filtros; con un solo país y el periodo por defecto, «No hay eventos sísmicos ahora mismo en <país>». Es `role="status"` y no roba el foco; además se muestra el aviso de información en la zona de avisos (solo uno de los dos se anuncia: el emergente `aria-hidden` al cerrarse y la zona de avisos como anuncio principal). Desaparece solo al llegar eventos.
- Fallo de fondo o capa: aviso de tipo aviso y vuelta a Simple; los eventos no se pierden.

## 7. Botón de tema
Flotante, sol y luna (SVG), `aria-label` «Cambiar a tema claro/oscuro» con el estado actual, alcanzable con teclado, foco visible. Alterna `dark`/`light`; la preferencia manual se guarda en el navegador (`localStorage`, tolerante a fallo); por defecto sigue el dispositivo (oscuro sin preferencia); sin animación con «reducir movimiento».

## 8. Lo que no cambia
Gráficos y tabla de la 009; ficha del evento; periodo, filtros, unidad y sin valor visibles; ND; «Sin país asignado»; «REPRODUCCIÓN» en estado, mapa, tabla y gráficos; refresco cada 60 s sin solapes; avisos de desactualizado y de backend inaccesible con la última lectura; accesibilidad (teclado, `aria-live`, axe-core
0 violaciones en ambos temas); el panel nunca consulta USGS; solo usa la API de la 006; teselas y placas no pasan por el túnel.
