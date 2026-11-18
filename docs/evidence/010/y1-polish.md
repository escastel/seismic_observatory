# Retoques de legibilidad posteriores al merge (2026-11-18)

Cuatro defectos señalados por la usuaria con capturas, corregidos y comprobados con Chrome y la API local (datos en [y1-polish-details.json](y1-polish-details.json)); axe-core (WCAG A y AA) sin violaciones en mapa, tabla y aviso emergente, en oscuro y claro.

| Defecto | Causa | Corrección | Observado |
|---|---|---|---|
| Títulos «Mapa base» y «Capas» ilegibles en claro | eran `<legend>` de un `fieldset`, que se dibuja sobre el borde y medio texto quedaba sobre el mapa | grupos `role="group"` con el título dentro de la caja | texto `rgb(66,89,108)` sobre fondo blanco (claro) y `rgb(169,185,200)` sobre fondo oscuro; legibles en ambos |
| «Ver ficha» ilegible en oscuro | el botón de la tabla no tenía estilos (colores del navegador) | fondo, texto y borde con los tokens; sin saltos de línea | oscuro: texto `rgb(232,238,244)` sobre `rgb(26,42,59)`; claro: `rgb(19,43,64)` sobre `rgb(228,236,241)`; 79×31 px. «Cargar más» recibe los mismos estilos |
| Aviso de «sin eventos» confundible con la leyenda | misma superficie neutra | fondo ámbar tintado (20 % del color de información), borde y franja ámbar | claramente distinto de la leyenda en ambos temas |
| Leyenda con demasiado texto al desplegarla | explicación siempre visible | al desplegar se ven los colores de profundidad y la barra de calor; la explicación queda en «Ver más detalles» | verificado con Satélite, calor y agrupación activos |

**No comprobado**: contraste en el canvas del mapa (axe no lo evalúa) ni con un lector de pantalla real.
