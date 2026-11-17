# Guía de validación (009)

Cada escenario se ejecuta con la skill `verify-stack` y deja esperado/observado y capturas en `docs/evidence/009/`. Nada se da por superado sin esa evidencia.
Orígenes de datos como en la 007: API real del stack local (`apiUrl` de `frontend/public/config.json` cambiado temporalmente y restaurado) y, solo para lo que el sistema real no puede producir
(nulos, 503, más de 1.000 eventos), el simulador de contrato de la 007. Navegador: Chrome con Puppeteer (emulación de `prefers-color-scheme`, `prefers-reduced-motion` y móvil) y axe-core.

**Requisitos**: stack levantado y datos de 2025 cargados; `cd frontend && npm ci && npm test`; `npm start` (puerto 4200) o `npm run build`.

| # | Escenario | Acción | Esperado |
|---|---|---|---|
| W1 | Tema por defecto y del dispositivo | abrir con `prefers-color-scheme: dark`, `light` y sin emulación | oscuro con dark y sin preferencia; claro con light; panel, mapa simple, gráficos y tarjetas coherentes |
| W2 | Cambio de tema en vivo | cambiar la emulación con el panel abierto | cambia sin recargar, sin perder la lectura (misma hora de última lectura y mismos eventos) |
| W3 | Fondos | elegir Simple, Relieve y Satélite en ambos temas | el fondo cambia; los eventos son legibles; atribución visible; Simple y Relieve con variante por tema |
| W4 | Límites de placas | elegir Relieve; quitar y poner la capa; probarla sobre Simple | línea discontinua visible en ambos temas; atribución PB2002; solo se descarga `placas.geojson` al activarla |
| W5 | Mapa de calor | activar en cada fondo con un periodo de 2025 (18.302 eventos, 1.000 dibujados) | capa visible y rótulo «Muestra: 1000 de 18302»; con 24 h (≤ 1.000) «Todos los eventos del periodo» |
| W6 | Agrupación | activar con el mismo periodo | grupos con recuento; sin círculos sueltos; mismo rótulo de muestra; al acercarse se separan |
| W7 | Fallo de fondo | bloquear el dominio de teselas de relieve y de satélite | aviso en región de estado, vuelta al mapa simple y eventos intactos |
| W8 | Tarjetas | comparar las cinco tarjetas con `GET /api/estadisticas` y el estado, con 3 conjuntos de filtros | cada cifra coincide; ND donde no hay dato; sin tarjeta de magnitud máxima |
| W9 | Gráficos y tablas | revisar los cuatro gráficos en ambos temas y su tabla | título, unidad, periodo, filtros y sin valor; colores del tema; tabla completa; «Sin país asignado» presente; «REPRODUCCIÓN» en reproducción |
| W10 | Ficha del evento | abrir desde un círculo, un grupo y la tabla; con un evento sin país y con valores nulos (simulador); con texto con marcas | datos y unidades correctos, ND, «Sin país asignado»; foco gestionado y Escape; el texto con marcas se ve literal (`window.__xss` sin definir) |
| W11 | Reducir movimiento | emular `prefers-reduced-motion: reduce` y abrir fichas, cambiar capas | ninguna animación de movimiento |
| W12 | Accesibilidad | axe-core (WCAG 2.0/2.1 A y AA) en claro y oscuro; recorrido con teclado; contraste de profundidad | 0 violaciones en ambos temas; todo operable con teclado; foco visible |
| W13 | No regresión de la 007 | repetir V1 a V15 de la 007, `npm test` y las pruebas de cierre y reapertura del túnel con el simulador | mismos resultados; las 106 pruebas anteriores siguen en verde |
| W14 | Móvil y peso | viewport de móvil y red lenta emulada; `npm run build` | sin desbordes horizontales; utilizable en menos de 5 s; peso inicial dentro de lo aprobado; Chart.js, calor, agrupación, placas y teselas solo al elegirse |
| W15 | Netlify y túnel (real) | desplegar o abrir el sitio de Netlify con el túnel; cerrar y reabrir el túnel; revisar con el inspector de ngrok | aviso con la última lectura y recuperación sin recargar; en el inspector solo peticiones a la API: **ninguna de teselas ni de placas** |
| W16 | Identidad | revisar cabecera, `<title>` y favicon en ambos temas | «seismicobservatory» y el logotipo (provisional o aprobado) con contraste suficiente |

Las pruebas de Vitest se ejecutan con `npm test`; las comprobaciones de navegador se guardan como JSON y capturas (`docs/evidence/009/`), igual que en la 007.
