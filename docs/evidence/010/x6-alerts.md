# X6. Avisos independientes (T023)

Sistema real (API local y panel con `ng serve`, Chrome con Puppeteer). Las situaciones se provocan interceptando las peticiones del navegador (red caída, 503, respuesta no válida, datos viejos, total mayor que lo recibido) y con la API real (periodo de más de 10 000 horas, Albania, reproducción). Datos crudos con tipo, rol, color de borde y texto en [x6-alerts.json](x6-alerts.json); capturas `x6-*.png`.

| Situación | Tipo / rol / color (oscuro) | Texto observado |
|---|---|---|
| Backend inaccesible | error / `alert` / rojo `rgb(255,107,107)` | «No se puede contactar con el backend. Se muestra la última lectura correcta. Se reintentará…» |
| Recuperación | éxito / `status` / verde | «Conexión recuperada…»; desaparece solo (sin avisos 9,5 s después) |
| Base de datos no disponible (503) | error / `alert` / rojo | «La base de datos no está disponible (503). Esto no significa que no haya eventos.» |
| Respuesta no válida de eventos | error / `alert` / rojo | «La respuesta de la API no es válida…» (ya no aparece junto al éxito anterior: se corrigió) |
| Estadísticas 422 | aviso / `status` / naranja `rgb(255,138,61)` | «Las estadísticas no están disponibles: … Se muestran los eventos de este filtro.» |
| Estadísticas no válidas | aviso / `status` / naranja | igual, con el motivo |
| Datos desactualizados | aviso / `status` / naranja | «hace 3 h 0 min» |
| Respuesta truncada | aviso / `status` / naranja | «Se muestran 202 de 4202 eventos…» |
| Periodo de más de 10 000 horas (API real) | dos avisos naranja | estadísticas no disponibles + «1000 de 33413 eventos» |
| Reproducción | información / `status` / ámbar `rgb(242,177,52)` | «Modo reproducción…» (con el truncado: 1000 de 2807) |
| Sin eventos (Albania) | información / `status` / ámbar | «No hay eventos sísmicos ahora mismo en Albania» |
| Teselas bloqueadas | aviso / `status` / naranja | «No se pudieron cargar las teselas del mapa; los eventos siguen visibles.» |
| Países no disponibles | aviso / `status` / naranja | «La lista de países no está disponible…» |
| Error de configuración | error / `alert` / rojo | «No se pudo leer config.json» |
| Claro, backend inaccesible | error / `alert` / rojo `rgb(192,48,47)` | mismo texto |

Cada aviso es un bloque independiente con icono SVG; sin avisos no ocupa espacio (`00-baseline`).

**Defecto encontrado y corregido**: tras recuperarse y volver a fallar, el aviso de éxito seguía visible junto al error nuevo; ahora el éxito se retira al fallar.
**Observado, no corregido**: el motivo del 422 de periodo largo llega en inglés desde la API («the period has 235645 hourly windows…»), tal como fija el contrato de la 006.
**Primer intento**: en la primera ejecución el caso «backend inaccesible» salió sin aviso mientras `ng serve` se recompilaba; repetido tres veces con el servidor estable, apareció siempre.
