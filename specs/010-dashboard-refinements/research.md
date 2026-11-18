# Investigación (Fase 0)

No quedan incógnitas. Hallazgos y decisiones, comprobados el 2026-11-18 con el sistema real.

## R1. Causa del fallo de «país sin eventos» (reproducido)

- **Reproducción**: con el panel de `main` contra la API local, al elegir Albania (`country_id=ALB`) y aplicar, el panel hace `GET /api/eventos?...country_id=ALB` (0 eventos) y `GET /api/estadisticas?...country_id=ALB`, y muestra
  «Aviso: los datos mostrados son la última lectura correcta» con «La respuesta de la API no es válida: period.end» y **203 eventos** (los de antes).
- **Causa**: `api/app/stats.py::hourly_counts` deduce el fin del periodo del último evento encontrado (`high`). Sin eventos, `high` es `None`; si no se dio `end`, el fin queda `None` y la respuesta lleva
  `"period": {"start": …, "end": null, …}`. El contrato (`specs/006-query-api/contracts/api.md`) fija `period.start` y `period.end` como números en las estadísticas. El adaptador del panel (`adaptStatistics`, `reqNum`) rechaza la respuesta y, al ser
  un fallo que no es `invalid_parameters`, el servicio descarta **todo** el refresco y conserva la lectura anterior (`fail()`).
- **Decisión (API)**: en `hourly_counts`, si no hay `end` ni eventos, `end = now`; si tampoco hay `start` (modo reproducción sin filtro de inicio y sin eventos), `start = end`. Así el periodo siempre tiene dos números; en modo en vivo con el periodo por
  defecto salen 24 ventanas a cero. No cambia ningún otro caso. Es una corrección que **hace cumplir** el contrato, no lo cambia (FR-023, FR-028).
- **Decisión (panel)**: tolerancia en `observatory.service.ts`: un fallo de **respuesta no válida** de las estadísticas se trata igual que un 422 de estadísticas (`statsFailure`), de modo que los eventos de ese filtro se muestran y la lectura anterior no se
  conserva. Un fallo de red o 503 sigue descartando el refresco (hay que conservar la última lectura, pruebas 9 y 10). La decisión vive en una función pura `statsFailureKeepsEvents` (R7).
- **Alternativas descartadas**: parchear solo el panel (dejaría la API incumpliendo su contrato); aceptar `end: null` en el adaptador (cambiaría el contrato del cliente).

## R2. Avisos: tipos, colores y roles

| Tipo | Color (token) | Icono | Rol anunciado | Casos |
|---|---|---|---|---|
| Error | rojo (`--alert-error`) | ✕ en círculo | `role="alert"` (asertivo) | backend inaccesible, base no disponible, error de configuración |
| Aviso | naranja intenso (`--alert-warning`) | ▲ | `role="status"` | datos desactualizados, respuesta truncada, periodo demasiado largo, fallo de estadísticas, fallo de fondo o capa |
| Información | color de la marca, ámbar (`--alert-info`) | ⓘ | `role="status"` | modo reproducción, sin eventos para el filtro |
| Éxito | verde (`--alert-success`) | ✓ | `role="status"`, caduca a los 8 s | recuperación del backend |

- Cada aviso es un bloque independiente (borde izquierdo de color, icono y texto); orden de apilado: error, aviso, información, éxito. El texto usa el color de texto normal sobre una superficie ligeramente teñida: el contraste de lectura lo da el texto y el color
  (≥ 3:1 frente a la superficie) refuerza el borde y el icono, no es la única señal.
- Tonos (a ajustar con capturas): oscuro — error `#ff6b6b`, aviso `#ff8a3d`, información `#f2b134`, éxito `#3ecf8e`; claro — error `#c0302f`, aviso `#b85a00`, información `#8a5a00`, éxito `#0f8a5f`.
- El aviso de «sin eventos» es de **información** y aplica a **cualquier** filtro sin resultados (no solo a un país), en vivo, en otro intervalo o en reproducción. Se muestra además como **aviso emergente** flotante sobre el mapa (no modal; no bloquea el teclado ni los lectores), con las condiciones aplicadas y la sugerencia de ampliar el periodo o quitar filtros; el anuncio a lectores de pantalla lo hace la zona de avisos (el emergente es `aria-hidden`).

## R3. Barra de estado

- Cinco métricas (Eventos, Última ingesta, Estado, Periodo UTC, Sin valor) con los textos de `lib/summary.ts` (ya probado); «Detalles» (`<details>`/botón accesible) con última lectura correcta del panel, generación de la respuesta, última ingesta (con la
  nota de modo reproducción), cuarentena y «eventos sin magnitud». En ≤ 760 px se ven Eventos, Última ingesta y Estado; Periodo y Sin valor pasan a «Detalles».
- Sustituye a `status/` y a `summary/`; los mensajes de `lib/status.ts` (`derivePanelStatus`) pasan a la zona de avisos; la lógica de `status.ts` no cambia.

## R4. Filtros

- La misma lógica (`filters.component.ts`, `lib/filters.ts`); cambia la presentación: cabecera con el título «Filtros», controles en una fila con `flex-wrap` y, en móvil, un botón «Filtros» que despliega el formulario; chips de los filtros **aplicados** (los de la última
  lectura, no los del formulario) generados por `lib/filter-chips.ts`: modo, periodo, magnitud mínima, país.

## R5. Mapa

- **Fondos**: solo `simple` y `satellite`; se retira `relief` del catálogo, del selector, las pruebas, la atribución de Esri y el pie de página. `platesDefault` pasa a `true` para ambos y las placas son una capa opcional sobre cualquiera.
- **Calor**: `leaflet.heat` con degradado propio `{0.2:#ffe066, 0.4:#ffb347, 0.6:#ff7a3d, 0.8:#e03b2e, 1.0:#8b0f1c}`, `radius` 28–32, `blur` 20, `minOpacity` 0,45 y peso por magnitud; leyenda de color en el control del mapa («Menos eventos → Más»); rótulo
  «Densidad de eventos de la muestra · N de TOTAL». Causa de lo poco visible actual: degradado por defecto, `radius: 18`, sin `minOpacity`.
- **Agrupación**: causa del «solo números»: no se cargó el CSS de `leaflet.markercluster`, y los iconos por defecto no tienen fondo. Decisión: `iconCreateFunction` propio con `L.divIcon` cuyas clases (`so-cluster`, nivel por recuento) se definen en `styles.css`
  (estilos globales, porque Leaflet crea los iconos fuera del componente): `lib/cluster-style.ts` da tamaño (34, 44, 54, 64 px) y nivel de color (amarillo, naranja, rojo) por recuento (< 10, < 50, < 200, ≥ 200); anillo y cifra. Los eventos sueltos añaden un halo
  (círculo mayor, baja opacidad) detrás del círculo de color de profundidad, igual brillo que las burbujas.
- **Leyendas**: como el mockup, dentro del mapa (control abajo a la izquierda, plegable en móvil): profundidad, tamaño y ND, agrupación y calor; selector de fondo y capas arriba a la derecha; chip de muestra arriba a la izquierda. El aviso de «sin eventos» se repite sobre el mapa de
  forma visual (`aria-hidden`) y se anuncia por la zona de avisos.
- **Alto**: `clamp(420px, 62vh, 760px)`; en móvil `56vh` con mínimo 340 px.

## R6. Botón de tema

- `ThemeService` guarda `preference: 'auto' | 'dark' | 'light'` (clave `seismic-theme` en `localStorage`, con `try/catch` en lectura y escritura) y expone `theme` = preferencia manual o, en `auto`, la del dispositivo (oscuro por defecto). Pone `data-theme` en `<html>` solo con preferencia manual.
- `styles.css`: oscuro como base; claro bajo `@media (prefers-color-scheme: light) { :root:not([data-theme="dark"]) { … } }` y bajo `:root[data-theme="light"]`; así sin JavaScript el panel sigue al dispositivo.
- Botón flotante (abajo a la derecha): `<button>` con `aria-label` «Cambiar a tema claro» o «Cambiar a tema oscuro», icono sol o luna (SVG), foco visible, transición solo con movimiento permitido. Cambia el tema de mapa y gráficos porque estos leen `theme()`.
- **Alternativa descartada**: selector de tres opciones (dispositivo, claro, oscuro); la usuaria pidió un botón sol/luna.

## R7. Tolerancia a fallos de estadísticas (función pura)

`lib/stats-tolerance.ts::statsFailureKeepsEvents(failure)`: `true` para `invalid_parameters` y `invalid_response`; `false` para `unreachable` y `database_unavailable`/5xx. El servicio la consulta en lugar del `if` actual (cambio mínimo y documentado en `observatory.service.ts`).

## R8. Cabecera

`app.component.html`: sin `eyebrow` ni `tagline`; `<h1><span class="brand-s">Seismic</span> Observatory</h1>`; `index.html` con `<title>Seismic Observatory</title>`. La nota «el panel nunca consulta USGS» sigue siendo cierta y queda en el pie de página («Datos sísmicos: USGS, procesados por el backend del proyecto»).

## R9. Orquestación

Sesión principal: corrección de la API y su prueba, `observatory.service.ts`, `map.component.*`, integración en `app.component.*`, `styles.css`, navegador real, evidencias, memoria. Sonnet: lógica pura con pruebas y componentes autocontenidos (avisos, barra, botón de tema, filtros).
Haiku: README de la evidencia. Cada agente toca solo los ficheros de su tarea, sin commit.

## R10. Qué no cambia

Gráficos y tabla (009), ficha del evento, `adapt.ts`, `api-types.ts`, `filters.ts`, `status.ts`, `config.ts`, el contrato de la API y el modelo. Sus pruebas siguen en verde (las de `status.ts` y `summary.ts` se conservan: la lógica se reutiliza).
