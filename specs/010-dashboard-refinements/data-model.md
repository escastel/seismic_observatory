# Modelo de datos (Fase 1)

Sin datos nuevos ni cambios de base de datos o de contrato. Entidades de **presentación** calculadas desde lo que el panel ya recibe (`Reading`, `Statistics`, `EventsMetadata`, `PanelStatus`, `ApiFailure` de `lib/api-types.ts` y `lib/status.ts`).

## Alert
| Campo | Regla |
|---|---|
| `id` | estable por causa (`unreachable`, `stale`, `truncated`, `period_too_long`, `stats_failed`, `layer_failed`, `replay`, `no_events`, `recovered`, `config`, `countries_unavailable`) para no duplicar |
| `kind` | `error` \| `warning` \| `info` \| `success` |
| `text` | español; sin HTML |
| `role` | `alert` solo para `error`; `status` para los demás |
| `autoDismissMs` | `8000` solo para `success`; el resto persiste mientras persista la causa |
| orden | error, warning, info, success; dentro de cada tipo, por prioridad de `PRIORITY` de `status.ts` |
Derivación (función pura `buildAlerts`): de `PanelStatus` (claves y mensajes), de `statsFailure`, del truncado (`events.length < total`), del modo reproducción, de que la lectura sea correcta con `total = 0` (texto con el nombre del país si hay filtro de país) y de los avisos de capas que emite el mapa.

## StatusBar
| Campo | Regla |
|---|---|
| `metrics` | cinco `SummaryCard` de `lib/summary.ts` (`total`, `lastIngestion`, `status`, `period`, `unvalued`); `ND` sin dato; etiqueta «REPRODUCCIÓN» en modo reproducción |
| `visibleOnNarrow` | `total`, `lastIngestion`, `status` |
| `details` | última lectura correcta del panel, generación de la respuesta, última ingesta, última reproducción (solo reproducción), cuarentena (total y geometría no válida), eventos sin magnitud (incluidos o excluidos) |
Fuente: solo la API (`Statistics`, `EventsMetadata`) y `PanelStatus`; nunca la muestra del mapa.

## FilterChip
`{ id, label }` para el modo, el periodo, el mínimo de magnitud y el país de los filtros **aplicados** (`reading.filters`); `Todos los países` y `Sin mínimo de magnitud` cuando no hay filtro; texto sin HTML.

## ThemePreference
| Campo | Regla |
|---|---|
| `preference` | `'auto'` (por defecto) \| `'dark'` \| `'light'`; solo `'dark'` y `'light'` se guardan |
| `theme` | `preference` si es manual; en `auto`, el del dispositivo; oscuro si no hay preferencia o no se puede leer |
| almacenamiento | `localStorage` con tolerancia a fallo de lectura y de escritura (el tema cambia igualmente) |
Transición: el cambio del dispositivo solo afecta en `auto`; el botón alterna entre `dark` y `light`.

## ClusterStyle
`{ size, level }` por recuento: `< 10` → 34 px y nivel 1 (amarillo); `< 50` → 44 px y nivel 2 (ámbar naranja); `< 200` → 54 px y nivel 3 (naranja rojizo); `≥ 200` → 64 px y nivel 4 (rojo). Anillo y cifra siempre.

## Lectura de un filtro (invariante)
Una `Reading` contiene los eventos y las estadísticas **del mismo** `filters`. Un refresco que no devuelve eventos válidos no la sustituye (se conserva la anterior con su aviso de error). Un refresco con eventos válidos y estadísticas inválidas la sustituye por una nueva con
`statistics = null` y `statsFailure` anotado; nunca mezcla eventos de un filtro con estadísticas de otro.
