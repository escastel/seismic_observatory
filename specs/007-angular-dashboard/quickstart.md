# Quickstart de verificación: panel Angular (spec 007)

Cada escenario se ejecuta con el sistema real (skill `verify-stack`) y un navegador, y deja su
resultado esperado y observado, con captura de los filtros usados, en `docs/evidence/007/`.
Contratos: [api.md](../006-query-api/contracts/api.md) y [ui-contract.md](contracts/ui-contract.md).

## Requisitos

- `.env` derivado de `.env.example` con `CORS_ORIGINS` que incluya `http://localhost:4200`.
- `docker compose up --build -d` con los servicios sanos; datos reales cargados (specs 003/004) y la
  selección de reproducción de la 005 para V9–V10. En Git Bash, `MSYS_NO_PATHCONV=1` con rutas de
  contenedor.
- `frontend/public/config.json` con `apiUrl` `http://127.0.0.1:8000` (local) o la URL del túnel.
- `cd frontend && npm ci && npm test && npm start`; abrir `http://localhost:4200`.

## Escenarios

| Id | Qué comprueba | Cómo | Esperado |
|---|---|---|---|
| V1 | Carga con la API de la 006 | abrir el panel | sin errores en consola (sin NG0900); mapa y tabla con eventos de 24 h; gráficos con datos |
| V2 | Evento nuevo | inyectar un evento válido (como en V3 de la 006) y esperar un refresco | aparece en mapa y tabla sin recargar, sin duplicar |
| V3 | Nulos como ND | evento con magnitud y otro con profundidad nulas | ND en ficha y tabla, nunca 0 ni `undefined`; distribuciones lo cuentan aparte |
| V4 | Evento marítimo | evento sin país | «Sin país asignado» en ficha, tabla y gráfico por país; no está en el selector |
| V5 | Texto como texto | evento con `place` que contenga marcas | se muestra literal, sin interpretarse |
| V6 | Truncado y paginación | periodo con más de 1.000 eventos; «Cargar más» hasta agotar | aviso de truncado; «Mostrando N de TOTAL»; sin repetidos; estadísticas = `total` de la API |
| V7 | Filtros coherentes | batería: solo fecha, `min_mag`, país, combinados | total de tabla = eventos de mapa (si no truncado) = `total` de estadísticas; periodo en UTC |
| V8 | Filtros inválidos | inicio ≥ fin; periodo > 10.000 h | mensaje por campo / explicación del 422; la última vista válida se conserva |
| V9 | Reproducción | cambiar a «Reproducción» | etiqueta de `metadata.label` en las cuatro zonas; `last_replayed_at` visible; sin ventana de 24 h; mapa y tabla anteriores vaciados |
| V10 | Aislamiento | totales reales → reproducción → volver | los totales reales son idénticos; nunca hay mezcla |
| V11 | Cerrar y reabrir el túnel | parar la API (o el túnel) y esperar un refresco; volver a levantarlo | aviso «backend inaccesible» con la última lectura rotulada y su hora; sin recarga, se recupera en el siguiente refresco |
| V12 | Estados distintos | parar `postgres`; usar parámetro inválido; esperar sin ingesta | mensajes distintos: 503, `degraded`, 422, desactualizado |
| V13 | Sin solapes y timeout | respuesta lenta forzada | una sola petición en curso; a los 15 s pasa a inaccesible |
| V14 | Teclado y lector | recorrer filtros, modo, tabla y «Cargar más» solo con teclado | foco visible; estados anunciados; la tabla sustituye al mapa |
| V15 | Despliegue | `npm run build`; servir `dist/observatorio/browser` | arranca con la configuración; sin secretos en el paquete |

Las pruebas con Netlify y el túnel ngrok reales las ejecuta la usuaria con el procedimiento del
README; la evidencia local usa `http://localhost:4200`.
