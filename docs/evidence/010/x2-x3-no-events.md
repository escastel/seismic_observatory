# X2 y X3. Filtro sin eventos (T015)

Sistema real: API local reconstruida con la corrección, panel con `ng serve` y Chrome (Puppeteer), 1440×900. Datos crudos en [x2-x3.json](x2-x3.json); capturas `x2-*.png`, `x3-*.png` y [x2-1-albania-popup-map.png](x2-1-albania-popup-map.png).

| Escenario | Esperado | Observado |
|---|---|---|
| Inicio, sin filtro | eventos y «Datos al día» | 202 eventos dibujados |
| Albania, periodo por defecto (0 eventos) | 0 eventos, aviso emergente, nada del filtro anterior | 0 eventos dibujados; emergente «No hay eventos sísmicos ahora mismo en Albania» con las cuatro condiciones y la sugerencia; aviso de información «Sin eventos para este periodo y estos filtros» |
| Quitar el país | vuelven los eventos, el emergente desaparece | 202 eventos, sin emergente |
| Magnitud mínima 9,5 | eventos del filtro | 10 eventos, sin emergente |
| Albania con `/api/estadisticas` sin `period.end` (simulador: solicitud interceptada) | 0 eventos del filtro nuevo y aviso de estadísticas, sin conservar la lectura anterior | 0 eventos dibujados, emergente y «las estadísticas no se han podido cargar (Respuesta no válida: period.end)» |
| Sin país, mismas estadísticas rotas | eventos visibles con aviso de estadísticas | 202 eventos y el aviso |

**Defecto encontrado y corregido durante la prueba**: el emergente estaba en el DOM pero tapado por los paneles de Leaflet (z-index 400–1000); se subió su `z-index` a 1100 y se verificó en la captura.

## Casos añadidos al cerrar T015 (API real, [t015.json](t015.json))

| Escenario | Esperado | Observado |
|---|---|---|
| Albania con 2025 completo | coincide con la API (`/api/estadisticas`: 3) | 3 eventos dibujados, barra 3, 3 filas, sin emergente ni avisos |
| Reproducción sin eventos (magnitud mínima 9,9) | 0 eventos, emergente y aviso de información; la API devuelve `period.start == period.end` numéricos | 0 eventos dibujados con «REPRODUCCIÓN»; emergente «No hay eventos registrados con las condiciones del filtro»; avisos de reproducción y de sin eventos; la API devuelve `start == end` (1795006085615) |

Capturas: `t015-albania-2025.png` y `t015-replay-empty.png`.
