# Investigación y decisiones: panel Angular (spec 007)

Cada decisión: qué, por qué y qué se descartó. Ningún punto queda sin resolver.

## R1. Revisar y dividir, no reescribir

**Decisión**: conservar el componente actual como punto de partida y extraer lo que cambia: lógica
pura a `lib/`, lectura a un servicio, y mapa, tabla, gráficos, estado y filtros a componentes
pequeños.
**Por qué**: el mapa (capas, `preferCanvas`, fronteras, popup como texto) funciona; lo roto es el
formato de datos y lo que falta es estado, modo y paginación. Un único fichero de 150 líneas ya
mezcla red, estado y dibujo y no se puede probar.
**Descartado**: reescribir con otra arquitectura (coste sin beneficio); dejar un solo componente
(las nuevas funciones lo harían intestable).

## R2. Pruebas: Vitest sobre lógica pura

**Decisión**: `vitest` como dependencia de desarrollo, versión exacta, ejecutado con `npm test`
sobre `src/app/lib/*.test.ts`. La navegación real se comprueba con el navegador y la API levantada.
**Por qué**: el proyecto no tiene pruebas; Karma exige Chrome headless y configuración en cada
equipo (Windows y Linux). Vitest corre en Node con TypeScript, sin Angular, y cubre lo que importa
(adaptar, formatear, derivar estado, construir parámetros).
**Descartado**: Karma/Jasmine (pesado y frágil entre equipos); pruebas de componentes con
Testing Library (más dependencias); Node `--test` con `--experimental-strip-types` (varía entre
Node 22.12 y 24 y obliga a importar con extensión `.ts`).

## R3. Contrato de lectura y adaptación

**Decisión**: `adapt.ts` valida la forma mínima de cada respuesta del contrato de la 006
([contracts/api.md](../006-query-api/contracts/api.md)) y la convierte en tipos del panel; una
forma inesperada lanza un error propio que el estado muestra como «respuesta no válida» y que no
rompe la interfaz (FR-004). Nulos se conservan como `null`; el formato (ND) se aplica solo al
mostrar.
**Por qué**: la causa del NG0900 actual es leer campos que ya no existen. Validar en el borde evita
que un cambio de la API vuelva a romper el pintado.
**Descartado**: confiar en tipos de TypeScript sin validar en ejecución; añadir una biblioteca de
esquemas (dependencia nueva para un contrato de tres endpoints).

## R4. Filtros: un objeto, tres vistas, UTC

**Decisión**: `QueryFilters {mode, start, end, minMag, countryId, excludeSynthetic}` es la única
fuente; `toParams()` genera la cadena de `/api/eventos` (más `limit`/`offset`) y de
`/api/estadisticas` (sin `limit`, `offset`, `format`). Fechas: dos campos de fecha y hora con
etiqueta «(UTC)»; el valor se interpreta con `Z` explícito, nunca con la zona del navegador.
Validación cliente: `start < end`, `min_mag` finito. Inicio inclusivo, fin exclusivo, como la API.
**Por qué**: principio VII y FR-012; `datetime-local` + `new Date(...)` interpreta en hora local, que
es el error ya detectado.
**Descartado**: dos constructores de parámetros (se desalinean); depender del 422 para todo (mala
experiencia; se usa como red de seguridad).

## R5. País: catálogo desde `paises.geojson`; «Sin país asignado»

**Decisión**: el selector se rellena con `ADM0_A3` y `NAME_ES` (fallback `ADMIN`) de `paises.geojson`
(177 entidades), ordenados por nombre; `country_id` de la base es `ADM0_A3` (`consumer/app/spatial.py`).
«Sin país asignado» no es opción: se explica con un texto junto al selector y se ve en ficha, tabla
y análisis por país.
**Por qué**: el fichero ya se descarga para las fronteras; el contrato no permite filtrar por
identificador nulo y no se simula en el cliente (FR-013, principio VIII).
**Descartado**: endpoint de catálogo nuevo en la API (superficie nueva sin necesidad demostrada);
filtrar «sin país» en cliente (rompería la coherencia de totales, porque la API no lo haría).

## R6. Ciclo de refresco, sin solapes y descarte de respuestas viejas

**Decisión**: un temporizador de `setTimeout` que se rearma al terminar cada ciclo (nunca dos a la
vez). Cada ciclo hace `eventos` (primera página) + `estadisticas` + `salud` en paralelo con un
`AbortSignal.timeout(requestTimeoutMs=15000)`. Cada consulta lleva un número de secuencia; al
cambiar filtros o modo se aborta lo pendiente, se incrementa la secuencia y se descarta cualquier
respuesta con secuencia anterior. Intervalo por defecto 60 000 ms; el mínimo de 30 s del panel
actual se sustituye por el valor de configuración con suelo de 5 s (para poder probar).
**Por qué**: FR-024 y FR-026; recuperación automática al volver el túnel porque el ciclo no se
detiene tras un fallo.
**Descartado**: `setInterval` (permite solapes); `rxjs` `interval`+`switchMap` (válido, pero el
ciclo propio con `fetch` es más simple y ya es la base del panel).

## R7. Estado derivado y última lectura rotulada

**Decisión**: `status.ts` es una función pura `(lectura, fallo, salud, ahora) → estado`. Prioridad:
backend inaccesible > 503 > 422 > salud `degraded` > desactualizado > sin eventos > normal; los
avisos se acumulan cuando son compatibles (p. ej. inaccesible + última lectura de hace N min).
Antigüedad = `generated` de la última respuesta menos `last_ingestion` cuando hay lectura reciente;
si no la hay, reloj local menos `last_ingestion`. Umbral `staleAfterMs`, por defecto 900 000
(15 min = 15 ciclos del productor de 60 s, `PRODUCER_INTERVAL_SECONDS`), configurable.
Una respuesta que no es JSON (p. ej. página intermedia de ngrok) cuenta como inaccesible.
**Por qué**: FR-021 a FR-025 y la edge case del reloj desajustado.
**Descartado**: comparar solo con el reloj del navegador; umbral fijo en código.

## R8. Modo y reproducción

**Decisión**: selector `Real | Reproducción`; `config.json.mode` (`live`|`replay`) es el modo
inicial. La petición lleva `mode`; la respuesta debe traer el mismo `metadata.mode` y, en `replay`,
`metadata.label`; si no, se rechaza (FR-030) y no se pinta. Al cambiar de modo: abortar, vaciar
mapa/tabla/gráficos/estado derivado, borrar la última lectura y pedir de nuevo. En `replay` se
muestra `last_replayed_at` y un conmutador «Excluir sintéticos»; el periodo es el elegido por el
usuario, sin ventana por defecto (la API no la aplica). La etiqueta se renderiza desde
`metadata.label`, no un texto fijo.
**Por qué**: principio VI y decisión previa de que la API emite la etiqueta.
**Descartado**: dos paneles separados; guardar ambas lecturas en memoria (riesgo de mezcla).

## R9. Mapa: una capa, texto como texto, coordenadas

**Decisión**: se conserva el patrón actual (construir la capa nueva y sustituir con `clearLayers`
+ `addLayer`), fichas con `textContent`, coordenadas validadas (`lon ∈ [-180,180]`, `lat ∈ [-90,90]`,
finitas); los omitidos se cuentan. Tamaño: radio creciente con la magnitud, mínimo con ND; color por
profundidad en tres tramos más gris para ND, con la leyenda ya existente ampliada con la forma:
el nulo se dibuja con borde discontinuo y se anuncia «ND» en ficha y tabla (FR-033). El control de
capas incluye una única capa «Terremotos».
**Por qué**: es lo que ya funciona y cumple FR-005 a FR-008; añadir solo lo que falta.

## R10. Tabla paginada y accesible

**Decisión**: `<table>` con `<caption>`, `<th scope="col">`, columnas id, hora UTC, magnitud, tipo
de magnitud, profundidad, lugar, país, continente, subregión y, en replay, `replayed_at` y sintético.
Carga la primera página (1000, el máximo de la API) y un botón «Cargar más» que sigue
`next_offset`; el texto «Mostrando N de TOTAL» sale de `count` acumulado y `total`. Un refresco
reinicia la tabla en la primera página y lo dice en la región de estado (simple y sin estados
intermedios incoherentes).
**Por qué**: FR-009/FR-010. Reiniciar en el refresco evita mezclar páginas de lecturas distintas.
**Descartado**: paginación virtual/infinita (complejidad); recargar todas las páginas cada 60 s
(carga innecesaria con decenas de miles de filas).

## R11. Gráficos propios sin biblioteca

**Decisión**: barras horizontales y de columnas con elementos HTML/SVG desde Angular, cada una con
su tabla de valores en un `<details>` y `role="img"` con descripción. Hora UTC: columnas
(máximo 10 000 ventanas por la API; si hay más de 168 barras se agrupa solo visualmente en la
tabla y se muestra el gráfico de los últimos 168 con aviso, sin recalcular cifras). País: las 15
principales + «Sin país asignado» siempre presente + «Otros» solo como suma de lo devuelto por
la API (no se recalcula nada que la API no diera, solo se suman filas ya entregadas para el
dibujo y la tabla completa queda disponible). Distribuciones: barras con «ND» aparte.
**Por qué**: FR-020; la tabla equivalente cubre daltonismo y lector de pantalla.
**Descartado**: añadir Chart.js/ngx-charts (dependencia con accesibilidad limitada y sin necesidad).
**Nota**: el agrupamiento visual de países y horas se limita a presentación; la tabla muestra todos
los valores tal como los entrega la API.

## R12. Despliegue y configuración

**Decisión**: `public/config.json` pasa a `{mode, apiUrl, refreshMs, skipNgrokWarning, staleAfterMs,
requestTimeoutMs}`; `mode: demo` y `terremotos-demo.geojson` se retiran (los sintéticos no pueden
confundirse con lo real). `netlify.toml` ya cumple (base `frontend`, publicación
`dist/observatorio/browser`); se revisa `_redirects` (regla SPA). La URL de `config.json` se
sustituye por la HTTPS del túnel antes de compilar (procedimiento en README); `CORS_ORIGINS` en
`.env` con el origen exacto de Netlify y `http://localhost:4200` (ya soportado por la 006).
**Por qué**: FR-034 a FR-037. El `apiUrl` actual del repositorio es un dominio ngrok de ejemplo
público: se revisa que no sea un secreto (no lo es; el authtoken sí lo sería y no está).

## R13. Accesibilidad

**Decisión**: idioma `es` en `index.html`; regiones `aria-live="polite"` para estado y `assertive`
solo para backend inaccesible; foco visible; etiquetas asociadas a cada campo; contraste ≥ 4,5:1
en texto; el mapa tiene alternativa en la tabla y el título enlaza a ella; información de
profundidad también en texto/ficha/tabla.
**Comprobación**: manual con teclado y revisión de contraste en la evidencia (sin herramienta
nueva).

## R14. Evidencia y navegador

**Decisión**: los escenarios V1–V12 de [quickstart.md](quickstart.md) se ejecutan con el stack
levantado (`verify-stack`) y un navegador real; cada uno guarda esperado, observado y una captura
con los filtros visibles en `docs/evidence/007/`. «Cerrar el túnel» se simula parando la API o el
túnel local; la prueba con Netlify real la hace la persona autora.
**Por qué**: principio IX y spec FR-039.
