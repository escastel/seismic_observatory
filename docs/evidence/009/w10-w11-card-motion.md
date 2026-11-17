# W10 y W11: ficha del evento y movimiento

Fecha: 2026-11-17. Chrome headless contra la **API real local**; las respuestas de `/api/eventos` se modificaron en el navegador (interceptación de peticiones, sin tocar la base de datos) para producir casos que el sistema real no genera. En bruto: [w-regression.json](w-regression.json) (`w10`).

| Caso | Esperado | Observado | Estado |
|---|---|---|---|
| Magnitud nula | «ND» en tabla y ficha | tabla «ND» y «Sin dato» (tipo); ficha «Magnitud ND» ([captura](w10-card-null-mag.png)) | SUPERADA |
| Profundidad nula | «ND» | tabla y ficha «ND» | SUPERADA |
| Sin país | «Sin país asignado» | tabla y ficha «Sin país asignado» | SUPERADA |
| Texto con marcas (`<img onerror=…> <b>…`) | texto literal, sin ejecutar | la ficha y la fila muestran el texto tal cual; 0 elementos `img` o `b` dentro del diálogo; `window.__xss` sin definir | SUPERADA |
| Coordenadas inválidas (999, 999) | omitido y contado | «208 eventos dibujados · 1 omitidos por coordenadas no válidas» | SUPERADA |
| Magnitud y profundidad negativas | se muestran con su valor | «-0,5 ml» y «-1,2 km» | SUPERADA |
| Magnitud 0 | se muestra 0 | «0,0 ml» | SUPERADA |
| Foco y teclado | foco inicial en «Cerrar», cierre con Escape y con el botón, retorno del foco al botón de la fila | foco en «Cerrar»; Escape cierra; el botón cierra; el foco vuelve al botón «Ver ficha» de la misma fila (abierta con teclado) | SUPERADA |
| Modo reproducción | hora de reproducción y «Sintético» en la ficha | «Hora de reproducción 2026-11-16 18:55:09 UTC · Sintético No sintético» ([captura](w13-replay.png)) | SUPERADA |
| Movimiento reducido (W11) | sin animación ni transición con `prefers-reduced-motion: reduce` | la ficha no tiene animación (`animation-name: none`, transición `0s`); las tarjetas, `0s` | SUPERADA |
| Errores de consola de la aplicación | ninguno | ninguno | SUPERADA |
