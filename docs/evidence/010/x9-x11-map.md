# X9 a X11. Mapa más visual (T024–T027)

Sistema real (API local, `ng serve`, Chrome con Puppeteer), periodo 2025 completo (1000 de 18 302 eventos) y periodo corto, tema oscuro y claro. Datos en [x9-x11.json](x9-x11.json); capturas `x9-*.png`.

| Comprobación | Esperado | Observado |
|---|---|---|
| Selector de fondo | solo Simple y Satélite | `["Simple","Satélite"]` en ambos temas |
| Placas por defecto | activadas sobre cualquier fondo | casilla marcada con Simple y tras cambiar a Satélite (`x9-dark-simple-2025-plates-default.png`, `x9-dark-satellite-clusters-plates.png`; el recuento de `path` es 0 porque se dibujan en canvas) |
| Mapa de calor visible | degradado amarillo–rojo oscuro, leyenda «Menos eventos → Más» y rótulo «densidad… · N de TOTAL» | canvas con 312 571 píxeles pintados (claro), rótulo «Densidad de eventos de la muestra · Muestra: 1000 de 18302», barra de leyenda presente (`x9-dark-heat.png`, `x9-light-heat.png`) |
| Agrupación en burbujas (antes: «solo números») | círculos de color con anillo y cifra, tamaño y color por recuento | 25 burbujas: 34 px amarillas (< 10), 44 px naranjas (< 50), rojas mayores; radio 50 %; clases `so-cluster--1..4` (`x9-dark-clusters.png`, `x9-light-clusters.png`) |
| Eventos sueltos con halo | halo tenue detrás del círculo de color de profundidad | visible en `x9-dark-short-circles-halo.png` y `x9-dark-satellite-circles-halo.png` |
| Sin Relieve ni Esri | ninguna referencia | `grep` en `frontend/src` y en `frontend/dist` sin coincidencias; los únicos dominios de teselas pedidos son `tile.openstreetmap.org` y `tiles.maps.eox.at`; pie de página y README actualizados |

**Pendiente a propósito**: `docs/report.md` conserva la descripción de Relieve en el apartado de la 009 (histórico); la sección nueva de la 010 la declara retirada (T035).
**Observado**: la leyenda abierta ocupa bastante mapa a 1440 px; es plegable.
