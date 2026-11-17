# Modelo de datos del panel (spec 007)

El panel no tiene base de datos; define tipos en memoria. Los tipos de la API vienen del contrato
de la 006 ([contracts/api.md](../006-query-api/contracts/api.md)). Los instantes son milisegundos
Unix UTC; `null` significa «sin valor» y se muestra como ND.

## Configuración (`public/config.json`)

| Campo | Tipo | Por defecto | Regla |
|---|---|---|---|
| `mode` | `live` \| `replay` | `live` | modo inicial; otro valor → error de configuración |
| `apiUrl` | URL https/http sin `/api` | — | sin barra final; se valida |
| `refreshMs` | entero | 60000 | suelo de 5000 |
| `requestTimeoutMs` | entero | 15000 | |
| `staleAfterMs` | entero | 900000 | umbral de «datos desactualizados» |
| `skipNgrokWarning` | booleano | `true` | envía `ngrok-skip-browser-warning` |

Sin secretos. `demo` ya no es un valor válido.

## QueryFilters (única fuente de las tres vistas)

| Campo | Tipo | Notas |
|---|---|---|
| `mode` | `live` \| `replay` | siempre se envía |
| `start`, `end` | instante UTC o `null` | `Z` explícito; inicio inclusivo, fin exclusivo; `start < end` |
| `minMag` | número finito o `null` | |
| `countryId` | `ADM0_A3` o `null` | nunca el nombre |
| `excludeSynthetic` | booleano | solo se envía en `replay` |

Derivados: `eventParams(limit, offset)` y `statsParams()`; ambos comparten el resto de campos.

## Respuestas adaptadas

- **EventsPage**: `metadata` (`generated`, `lastIngestion`, `mode`, `count`, `total`, `truncated`,
  `limit`, `offset`, `nextOffset`, `period`, `nullMagnitude`, `quarantined`, y en replay `label`,
  `lastReplayedAt`) y `events[]`.
- **MapEvent**: `id`, `lon`, `lat`, `depthKm|null`, `mag|null`, `magType|null`, `place`, `time`,
  `updated`, `countryId|null`, `countryName|null` (→ «Sin país asignado»), `continent|null`,
  `subregion|null`, y en replay `replayedAt`, `synthetic`.
- **Statistics**: `mode`, `metadata`, `scope`, `mapTruncated`, `period`, `filters`, `unit`, `total`,
  `hourly.items[{start,count}]`, `byCountry.items[{countryId|null,countryName,count}]`,
  `magnitudeDistribution{items[{from,to,count}],unvalued}`, `depthDistribution{items[{label,from,to,count}],unvalued}`,
  `comparison{recent,baseline,ratio|"ND",filtersApplied,warning}`.
- **Health**: `status` (`ok`|`degraded`), `database`, `replayDatabase`, `generated`, `lastIngestion|null`.
- **ApiFailure**: `kind` = `invalid_parameters` (422, con `param` y mensaje) | `database_unavailable`
  (503) | `server_error` (500) | `unreachable` (red, tiempo, no JSON, CORS) | `invalid_response`
  (forma inesperada o modo/etiqueta incoherentes).

## Lectura del panel (`Reading`)

`{ readAt, filters, events (acumulados de las páginas cargadas), pages, statistics, health }`.
Se sustituye completa tras una lectura correcta; tras un fallo se conserva y se rotula con `readAt`.
Al cambiar de modo se descarta.

## Estado del panel (`PanelStatus`)

Derivado por `status.ts`; combinación de:

| Clave | Cuándo | Aviso (español) |
|---|---|---|
| `ok` | lectura correcta, `status: ok`, ingesta reciente | Datos al día |
| `stale` | antigüedad de `last_ingestion` > `staleAfterMs` | Datos desactualizados (hace X) |
| `degraded` | salud `degraded` | Sistema degradado: base no disponible |
| `unreachable` | `unreachable` | Backend inaccesible: se muestra la última lectura (hora) |
| `database_unavailable` | 503 | La base de datos no está disponible |
| `invalid_parameters` | 422 | Filtro no válido: parámetro y motivo |
| `empty` | 200 con `count: 0` | Sin eventos para este periodo y filtros |
| `invalid_response` | respuesta incoherente | Respuesta no válida |

`stale` es compatible con `unreachable`/`database_unavailable` (la última lectura conservada).

## Transiciones

1. **Arranque**: configuración → catálogo de países y fronteras → primera lectura.
2. **Ciclo**: lectura (eventos + estadísticas + salud) → correcta: sustituye `Reading`; fallo: conserva
   `Reading` y activa el aviso; en ambos casos rearma el temporizador.
3. **Cambio de filtros**: aborta, secuencia+1, repite la lectura; si falla con 422 conserva la última
   vista válida.
4. **Cambio de modo**: aborta, secuencia+1, vacía todo (incluida `Reading`), lee en el nuevo modo.
5. **«Cargar más»**: añade la página de `next_offset` a la tabla de la misma lectura.
