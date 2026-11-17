# W13: no regresión (V1 a V15 de la 007 con el panel rediseñado)

Fecha: 2026-11-17. Chrome headless contra la compilación de producción y la **API real local**. Donde el sistema real no produce el caso, las respuestas se alteraron en el navegador (interceptación de peticiones; el repositorio y la base de datos no se tocan). En bruto: [w-regression.json](w-regression.json).

- `npm test`: 13 ficheros, **142 pruebas en verde** (las 106 anteriores más 36 nuevas).
- Ficheros que no se pueden tocar (`observatory.service.ts`, `adapt.ts`, `api-types.ts`, `filters.ts`, `status.ts`, `config.ts`), y también `format.ts`, `geo.ts` y `chart-data.ts`: sin diferencias con la rama `008-analysis-costs-deliverables`. Sin cambios en `api/`, `db/`, `consumer/` ni `producer/`.

| Id | Qué comprueba | Origen | Observado | Estado |
|---|---|---|---|---|
| V1 | Carga con la API real | real | 210 eventos en mapa, tabla y estadísticas; sin errores de aplicación en consola | SUPERADA |
| V3 | Nulos como ND | alterada | magnitud y profundidad nulas como «ND»; 0 sigue siendo 0 (ver [W10](w10-w11-card-motion.md)) | SUPERADA |
| V4 | Evento sin país | alterada | «Sin país asignado» en tabla y ficha; el gráfico por país lo trae como una fila más | SUPERADA |
| V5 | Texto como texto y coordenadas | alterada | texto literal; `window.__xss` sin definir; «1 omitidos por coordenadas no válidas» | SUPERADA |
| V6 | Truncado y paginación | simulada (2.500) | «Mostrando 1000 de 2500», aviso de respuesta truncada; tras dos «Cargar más», 2500 de 2500, 2500 filas únicas, botón deshabilitado | SUPERADA |
| V7 | Filtros coherentes | real | mapa, tabla, tarjetas y gráficos coinciden con la API en tres conjuntos de filtros y los dos temas ([W8](w8-w9-cards-charts.md)) | SUPERADA |
| V9 | Reproducción etiquetada | real | «REPRODUCCIÓN» en tarjetas, estado, mapa, tabla, gráficos y ficha; total 2.807 | SUPERADA |
| V10 | Aislamiento | real | total real antes y después de la reproducción: 210 y 210 | SUPERADA |
| V11 | Backend inaccesible y recuperación | alterada (peticiones abortadas, refresco de 3 s) | «No se puede contactar con el backend. Se muestra la última lectura correcta», 209 eventos conservados, tarjeta «Backend inaccesible» ([captura](w13-unreachable.png)); al volver, «Datos al día» sin recargar. Una respuesta HTML (página de ngrok) se trata también como inaccesible | SUPERADA |
| V12 | Estados distintos | alterada | 503: «La base de datos no está disponible (503). Esto no significa que no haya eventos» y tarjeta «Base de datos no disponible»; 422 de estadísticas: aviso de estadísticas no cargadas con los eventos intactos; desactualizado: «hace 40 min» y tarjeta «Desactualizado» ([captura](w13-stale.png)) | SUPERADA |
| V13 | Sin solapes y tiempo de espera | alterada (respuesta de 9 s, tiempo de espera 4 s) | máximo 1 petición de eventos en vuelo; el panel pasa a inaccesible con la última lectura conservada | SUPERADA |
| V14 | Teclado y axe | real | 0 violaciones axe en ambos temas; ficha operable con teclado (ver [W12](w12-a11y.json)) | SUPERADA |
| V15 | Build y secretos | local | `npm run build` sin errores; los 12 ficheros del paquete no contienen `authtoken`, `password` ni `secret` | SUPERADA |
| V2 | Evento nuevo sin recargar | real | cada refresco recarga sin navegar de página (los cambios de estado de V11 y V12 se produjeron sin recargar); no se esperó a un evento nuevo de USGS | PARCIAL |
| V8 | Filtros inválidos | | no se repitió (inicio ≥ fin y más de 10.000 h); el formulario y `filters.ts` no cambiaron | NO REPETIDA |

Pendiente: cierre y reapertura del **túnel real** y repetición en Netlify (T029).
