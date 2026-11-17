# W1 a W7 y accesibilidad (W12) — comprobación parcial en navegador real

Fecha: 2026-11-17. Chrome headless (Puppeteer, instalado fuera del repositorio) contra la compilación de producción servida en `http://localhost:4200`, con la **API real local** (`http://localhost:8000`, 211 eventos de las últimas 24 h). Resultados en bruto: [w-smoke.json](w-smoke.json), [w-extra.json](w-extra.json).

| Prueba | Esperado | Observado | Estado |
|---|---|---|---|
| Tema oscuro (W1) | fondo oscuro con `prefers-color-scheme: dark` | `body` `rgb(11, 21, 32)`; [captura](panel-dark.png) | SUPERADA |
| Tema claro (W1) | variante clara con `light`; filtro CSS del mapa desactivado | [captura](panel-light.png); filtro del fondo Simple `none` | SUPERADA |
| Fondos (W2) | Simple, Relieve y Satélite cargan teselas | 12, 18 y 18 teselas cargadas; filtro oscuro solo en Simple y Relieve ([relieve](map-relief-dark.png), [satélite](map-satellite-dark.png)) | SUPERADA |
| Placas con relieve (W3) | activadas por defecto con Relieve; no se piden antes | `placas.geojson` no se pide al cargar; con Relieve la casilla está marcada y se pide ([captura](relief-plates.png)) | SUPERADA |
| Calor y agrupación (W4/W5) | capas opcionales con rótulo de muestra | calor: 1 lienzo; agrupación: 10 grupos; rótulo «Todos los eventos del periodo» (211 de 211) ([captura](map-heat-cluster-dark.png)). Con un periodo truncado simulado (2.500) el rótulo pasa a «Muestra: 1000 de 2500» y, al cargar todo, a «Todos los eventos del periodo» ([captura](w4-sample-label.png)) | SUPERADA |
| Fallo de un fondo (W6) | aviso y vuelta a Simple, eventos intactos | con `arcgisonline.com` bloqueado: «No se pudo cargar el fondo «Relieve»; se vuelve al mapa Simple.», 211 eventos dibujados | SUPERADA |
| Carga diferida (W7) | Chart.js, calor, agrupación y placas no se piden hasta usarlos | al cargar solo se piden la app, `paises.geojson`, teselas OSM y el trozo de gráficos; calor, agrupación y placas llegan al activarlos | SUPERADA |
| Ficha (W10, datos reales) | diálogo con foco en «Cerrar» y Escape | `role="dialog"` `aria-modal`, foco en «Cerrar», se cierra con Escape ([captura](card-dark.png), [claro](card-light.png)). El retorno del foco no se pudo comprobar (el clic programático no da foco) | PARCIAL |
| Movimiento (W11) | sin transiciones con `reduce` | duración de transición `0s` | SUPERADA |
| Accesibilidad (W12) | axe-core WCAG A y AA sin violaciones | 0 violaciones en oscuro y en claro | SUPERADA |
| Móvil (W14) | sin desplazamiento horizontal a 390 px | tras corregir dos desbordes (rejilla de tarjetas y etiquetas ocultas de la tabla) el ancho de página es 390 = viewport ([captura](mobile.png)) | SUPERADA |
| Túnel (W15) | ninguna petición de teselas ni placas por ngrok | solo se comprobó que el panel no pide nada a un host `ngrok`; con la API local | PARCIAL |

## Sin comprobar todavía

- W8/W9: comparar cada cifra con `GET /api/estadisticas` en tres conjuntos de filtros (solo se vio que el total, 211, coincide).
- W10: evento sin país, valores nulos y texto con marcas (requiere el simulador de contrato de la 007, que no está en el repositorio).
- W13: repetir V1 a V15 de la 007.
- W14: peso inicial medido con red lenta (la medición hecha no es fiable y no se cita).
- W15: Netlify y túnel reales (el despliegue pide confirmación explícita).
- W16: identidad (logotipo aprobado por la usuaria) y contraste medido de los colores de profundidad.

## Pruebas unitarias

`npm test` en `frontend/`: 13 ficheros, 142 pruebas, todas en verde (las 106 anteriores más 36 nuevas). Los ficheros protegidos (`observatory.service.ts`, `adapt.ts`, `api-types.ts`, `filters.ts`, `status.ts`, `config.ts`) no tienen diferencias con la rama 008.
