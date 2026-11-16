# Contrato de la interfaz del panel (spec 007)

Qué muestra el panel y cómo reacciona. El contrato de datos es el de la 006
([api.md](../../006-query-api/contracts/api.md)); aquí solo se fija lo que el panel hace con él.
Todos los textos visibles están en español.

## Peticiones

| Vista | Petición | Parámetros |
|---|---|---|
| Mapa y tabla | `GET /api/eventos` | `mode`, `start`, `end`, `min_mag`, `country_id`, `exclude_synthetic` (solo replay), `limit=1000`, `offset` |
| Gráficos | `GET /api/estadisticas` | los mismos, sin `limit` ni `offset` |
| Estado | `GET /api/salud` | ninguno |

Cabecera `ngrok-skip-browser-warning: 1` si `skipNgrokWarning`. Sin cuerpo, cookies ni credenciales.
Tiempo máximo 15 s. Un refresco por ciclo; nunca solapados.

## Reglas de aceptación de una respuesta

1. 200 con JSON de la forma esperada, si no → `invalid_response` o `unreachable` (si no es JSON).
2. `metadata.mode` igual al pedido; en `replay`, `metadata.label` presente y no vacía.
3. Con secuencia anterior a la actual → se descarta sin pintar.
4. 422 → `invalid_parameters` con el `param` y el mensaje; 503 → `database_unavailable`; 500 →
   `server_error`; red, tiempo, CORS o no JSON → `unreachable`.

## Zonas de la pantalla

| Zona | Contenido | Accesibilidad |
|---|---|---|
| Estado | tres instantes rotulados (última lectura del panel, generación de la respuesta, última ingesta), periodo consultado, modo y etiqueta, avisos | `aria-live="polite"`; inaccesible en `assertive` |
| Filtros | modo, desde/hasta (UTC), magnitud mínima, país, excluir sintéticos (solo replay), aplicar y restablecer | etiquetas asociadas, errores junto al campo |
| Mapa | fondo, fronteras, capa «Terremotos», leyenda de profundidad y tamaño, contador de dibujados y omitidos | alternativa: la tabla |
| Tabla | caption, todos los campos, «Mostrando N de TOTAL», «Cargar más» | `th scope`, teclado |
| Análisis | horas UTC, países, magnitud, profundidad, comparación, cada uno con periodo, filtros, unidad y sin valor | tabla equivalente por gráfico |
| Aviso de truncado | «Se muestran N de TOTAL eventos; las estadísticas incluyen el total» | región de estado |

## Textos fijos

- Nulo: «ND». País nulo: «Sin país asignado».
- Reproducción: la etiqueta de `metadata.label` (hoy «REPRODUCCIÓN») en estado, mapa, tabla y
  análisis.
- Comparación: «ND» si `ratio` es `"ND"`; el `warning` de la API se muestra tal cual.
- 422 por periodo largo: «El periodo supera las 10.000 horas: acota las fechas».
- Backend inaccesible: «No se puede contactar con el backend. Se muestra la última lectura correcta
  (hora UTC). Se reintentará en el siguiente refresco».

## Orden de prioridad de avisos

`unreachable` > `database_unavailable` > `invalid_parameters` > `degraded` > `stale` > `empty` > `ok`.
Los compatibles se muestran juntos; la última lectura conservada siempre va rotulada con su hora.

## Mapa

- Una capa de eventos que se vacía y se reconstruye entera en cada lectura correcta; en un fallo no
  se toca.
- Radio creciente con `mag`; `mag` nulo: radio mínimo y borde discontinuo. Color por `depthKm`:
  < 70 km, 70–299,99 km, ≥ 300 km; nulo: gris con borde discontinuo; leyenda con las cuatro
  categorías y texto.
- Ficha (texto): id, magnitud, profundidad, hora UTC, país, continente, subregión; en replay también
  `replayed_at` y sintético.
- Coordenadas no finitas o fuera de rango → omitido y contado.

## Cambio de modo

Aborta lo pendiente → limpia capa, tabla, gráficos y última lectura → pide en el nuevo modo.
Nunca coexisten datos de ambos.
