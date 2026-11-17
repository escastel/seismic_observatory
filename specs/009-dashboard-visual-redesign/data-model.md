# Modelo de datos (Fase 1)

No hay datos nuevos ni cambios de API, base de datos o contrato. Son entidades de **presentación** que se calculan desde lo que el panel ya recibe (`Statistics`, `MapEvent`,
`metadata`, `SystemStatus` de `lib/api-types.ts` y `lib/status.ts`).

## Theme
| Campo | Regla |
|---|---|
| `value` | `'dark'` \| `'light'` |
| origen | `prefers-color-scheme` del dispositivo; **`'dark'` si no hay preferencia expresada o si no se puede leer** |
| `reducedMotion` | booleano de `prefers-reduced-motion: reduce` |
Transición: el cambio de preferencia actualiza el valor sin recargar ni perder la lectura.

## BaseLayer
| Campo | Regla |
|---|---|
| `id` | `simple` \| `relief` \| `satellite` |
| `label` | texto en español |
| `tiles(theme)` | URL de teselas y filtro CSS según el tema (`simple` y `relief` tienen variante clara y oscura; `satellite` es la misma) |
| `attribution` | texto obligatorio, siempre visible mientras el fondo esté activo |
| `maxZoom` | el del proveedor |
Por defecto: `simple`. Si falla la carga: se vuelve a `simple` y se avisa.

## OverlayLayer
| Campo | Regla |
|---|---|
| `id` | `circles` \| `heat` \| `cluster` \| `plates` |
| `enabled` | booleano; `circles` activo por defecto; `heat`, `cluster` y `plates` opcionales y combinables con cualquier fondo |
| `sampleLabel` | `«Muestra: N de TOTAL»` si `N < TOTAL`; `«Todos los eventos del periodo»` si `N = TOTAL` (solo `heat` y `cluster`) |
Regla: `cluster` y `circles` no se dibujan a la vez (la agrupación sustituye a los círculos sueltos); `heat` puede combinarse con cualquiera de los dos.

## SummaryCard
| Campo | Regla |
|---|---|
| `id` | `total` \| `lastIngestion` \| `status` \| `period` \| `unvalued` |
| `label`, `value` | texto en español; `value` = `ND` cuando no hay dato |
| `unit` | `eventos`, `UTC`, etc. |
| `detail` | filtros aplicados y, en `unvalued`, magnitud y profundidad sin valor por separado |
| fuente | solo `Statistics` y `SystemStatus` de la API; **nunca** la muestra del mapa |
No existe tarjeta de «magnitud máxima».

## ChartSeries
| Campo | Regla |
|---|---|
| `id` | `hourly` \| `country` \| `magnitude` \| `depth` |
| `title`, `unit`, `periodText`, `filtersText`, `unvaluedText` | obligatorios (principio VII) |
| `points` | `{ label, count }` en el orden de la API; el gráfico `hourly` dibuja la ventana de las últimas 168 horas y avisa del resto, y la tabla las contiene todas |
| `colors` | derivados de los tokens del tema; profundidad con la misma paleta que el mapa |
| `table` | filas equivalentes siempre disponibles |
| `label` | «REPRODUCCIÓN» en modo reproducción |

## EventCard
| Campo | Regla |
|---|---|
| campos | id, magnitud y tipo, profundidad, lugar, hora UTC, país, continente, subregión; en reproducción, hora de reproducción y sintético |
| valores ausentes | `ND`; país nulo: «Sin país asignado»; magnitud o profundidad negativas se muestran con su valor |
| origen | el `MapEvent` ya cargado; sin peticiones nuevas |
| texto | solo como texto (interpolación), nunca HTML |

## Brand
`name` = «seismicobservatory»; `logo` = «S» con onda sísmica (SVG, `currentColor`); `palette` = tokens por tema; `font` = pila del sistema. Provisional hasta que la usuaria apruebe el logotipo.
