# W8 y W9: tarjetas y gráficos frente a la API

Fecha: 2026-11-17. Chrome headless (Puppeteer) contra la compilación de producción y la **API real local**. Para cada conjunto de filtros se aplicó el filtro en el panel y se comparó con `GET /api/estadisticas` con los mismos parámetros. En bruto: [w-regression.json](w-regression.json) (`w8`).

| Tema | Filtros | Total API | Tarjeta «Eventos» | Tabla de «por hora» | Tabla de «por país» | Eventos dibujados | Estado |
|---|---|---|---|---|---|---|---|
| oscuro | sin filtros | 210 | 210 | 210 | 210 | 210 | SUPERADA |
| oscuro | magnitud mínima 2 | 76 | 76 | 76 | 76 | 76 | SUPERADA |
| oscuro | país USA + magnitud mínima 1 | 128 | 128 | 128 | 128 | 128 | SUPERADA |
| claro | sin filtros | 210 | 210 | 210 | 210 | 210 | SUPERADA |
| claro | magnitud mínima 2 | 76 | 76 | 76 | 76 | 76 | SUPERADA |
| claro | país USA + magnitud mínima 1 | 128 | 128 | 128 | 128 | 128 | SUPERADA |

- La tarjeta «Sin valor» coincide con `magnitude_distribution.unvalued` y `depth_distribution.unvalued` (0 y 0 en los seis casos) y su detalle nombra los filtros aplicados («magnitud mínima 1, país USA»). [Captura](w8-filtered-dark.png).
- Modo reproducción: tarjetas, estado, mapa, tabla y gráficos llevan «REPRODUCCIÓN»; el total de reproducción es 2.807 ([captura](w13-replay.png)).
- Las cifras de las tarjetas salen de `Statistics`, nunca de la muestra del mapa; no hay tarjeta de «magnitud máxima».
- No se comprobó la distribución de magnitud ni de profundidad fila a fila con la API; solo los totales y los «sin valor».
