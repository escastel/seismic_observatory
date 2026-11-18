# Guía de validación (010)

Cada escenario se ejecuta con la skill `verify-stack` y deja esperado/observado y capturas en `docs/evidence/010/`. Nada se da por superado sin esa evidencia. Orígenes de datos como en la 007 y la 009: API real del stack local (`apiUrl` de `frontend/public/config.json` cambiado
temporalmente y restaurado) y el simulador de contrato solo para lo que el sistema real no puede producir (nulos, 503, más de 1.000 eventos, respuesta no válida). Navegador: Chrome con Puppeteer (emulación de tema, movimiento y móvil) y axe-core.

**Requisitos**: stack levantado; `docker compose up --build -d api` tras el cambio de `stats.py`; `cd frontend && npm ci && npm test`; `npm start` (puerto 4200).

| # | Escenario | Acción | Esperado |
|---|---|---|---|
| X1 | Corrección de la API | `docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m pytest tests/query_api/test_statistics.py -q` y `GET /api/estadisticas?country_id=ALB` | la prueba nueva pasa; `period.start` y `period.end` son números y hay 24 ventanas a cero |
| X2 | Albania (real) | filtrar por Albania con el periodo por defecto; luego un país con eventos | mapa y tabla vacíos, total 0, aviso de información «No hay eventos sísmicos ahora mismo en Albania»; sin eventos de otro filtro; con un país con eventos, mapa, tabla y estadísticas coinciden |
| X3 | Estadísticas no válidas (simulador) | el simulador devuelve eventos válidos y estadísticas con `period.end` ausente | se muestran los eventos de ese filtro y un aviso de estadísticas; no se conserva la lectura anterior |
| X4 | Cabecera | abrir en ambos temas | «Seismic» en el color del logotipo y «Observatory» blanco (oscuro) o texto oscuro (claro); sin «BIG DATA · PROYECTO DE AULA» ni «Este panel nunca consulta USGS» |
| X5 | Orden y primera pantalla | 1440×900 y 390×844 | orden cabecera, avisos, barra, filtros, mapa; en escritorio caben cabecera, barra, filtros y ≥ 50 % de la altura del mapa; en móvil asoma el mapa |
| X6 | Avisos | provocar backend inaccesible (túnel parado o red bloqueada), datos desactualizados, 503, truncado (periodo largo), periodo > 10.000 h, fallo de fondo (dominio bloqueado), reproducción, sin eventos y recuperación | cada aviso es un bloque independiente sobre la barra con su color, icono, texto y rol; el de éxito caduca; error y desactualizado conservan la última lectura |
| X7 | Barra de estado | comparar las cinco métricas con `/api/estadisticas` y `/api/eventos` en tres juegos de filtros; abrir «Detalles»; viewport móvil | cifras iguales; ND sin dato; Detalles distingue lectura del panel, generación e ingesta; en móvil tres métricas y el resto en Detalles |
| X8 | Filtros | revisar la fila en 1440 px, con ancho reducido y en móvil | una sola línea con título «Filtros» en escritorio; chips de los filtros aplicados; botón «Filtros» en móvil; validación como en la 007 |
| X9 | Fondos y placas | selector de fondo y capas en ambos temas | solo Simple y Satélite; placas activadas por defecto sobre ambos y desactivables; ninguna referencia a Relieve ni a Esri en la interfaz, el pie ni el paquete |
| X10 | Calor | activar sobre cada fondo y tema con un periodo largo (2025) y uno corto | degradado amarillo→rojo oscuro claramente visible, leyenda de colores, rótulo «Muestra: 1000 de 18302» / «Todos los eventos del periodo» y «densidad de eventos de la muestra» |
| X11 | Agrupación | activar con 2025 y con 24 h | burbujas con cifra, anillo, tamaño y color por recuento; sueltos con color de profundidad y halo; mismo rótulo de muestra; al acercarse se separan |
| X12 | Botón de tema | pulsar, recargar, con `localStorage` bloqueado, con teclado y con «reducir movimiento» | cambia sin recargar y conserva la lectura; la elección persiste tras recargar; funciona sin almacenamiento; nombre y estado accesibles; sin animación con movimiento reducido |
| X13 | Accesibilidad | axe-core (WCAG A y AA) en ambos temas, con avisos visibles y «Detalles» abierto; recorrido con teclado | 0 violaciones; contraste de avisos y de burbujas suficiente; todo operable con teclado |
| X14 | No regresión | `npm test` completo, V1 a V15 de la 007, escenarios W de la 009 y cierre y reapertura del túnel con el simulador | mismos resultados; las pruebas anteriores siguen en verde |
| X15 | Peso y red | `npm run build`; inspector de ngrok con el panel abierto | peso inicial sin crecer respecto a la 009; solo `/api/*` por el túnel; ninguna petición de teselas ni de placas |
| X16 | Netlify y túnel (tras el merge) | abrir el sitio de Netlify, filtrar por Albania, cerrar y reabrir el túnel | mismos resultados que en local; recuperación sin recargar |

Las pruebas de Vitest se ejecutan con `npm test`; las comprobaciones de navegador se guardan como JSON y capturas (`docs/evidence/010/`), como en la 007 y la 009.
