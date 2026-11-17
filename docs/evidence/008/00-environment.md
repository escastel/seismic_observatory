# Entorno de la verificación (spec 008)

**Fecha**: 2026-11-17 · **Rama**: `008-analysis-costs-deliverables` (desde `007-angular-dashboard`; la 007
aún no está en `main`) · **Equipo**: Windows 11 Pro for Workstations 10.0.26200, Git Bash, Intel Core
i5-11400H (2,70 GHz, 12 hilos lógicos), 15,7 GB de RAM (7,6 GiB visibles para Docker/WSL2), Docker
Desktop 29.1.3 · **Servidor**: PostgreSQL 16.4 (Debian 16.4-1.pgdg120+2).

## Estado del stack (T001)

`producer`, `consumer`, `kafka`, `postgres` y `api` en `healthy`; `tunnel` en marcha. Las variables de
PostgreSQL se expanden dentro del contenedor; no se lee ni se imprime `.env`.

## Datos de partida (solo lectura, 2026-11-17 14:32 UTC)

| Dato | Valor |
|---|---|
| `core.event_current` | 34.207 eventos, de 2025-01-01 00:13 UTC a 2026-11-17 14:21 UTC |
| de ellos con identificador `synthetic-%` | **1.013** (restos de las pruebas de escala de la 002; fuera del análisis real) |
| sin magnitud / sin profundidad | 2 / 1 |
| `replay.event_current` | 2.807 eventos (REPRODUCCIÓN; fuera del análisis real) |
| esquema `bench` | no existe |

**Consecuencia para el análisis**: toda consulta SQL del análisis debe excluir `event_id LIKE 'synthetic-%'`
(la API en modo real ya lo hace por defecto, spec 006 R2). El catálogo de 2025 solo tiene magnitud ≥ 4.

## Pruebas de §11 y entregables de §12 (T002)

Leídos del enunciado local (`§8`, `§10` a `§13`). Las 11 pruebas de §11: (1) evento nuevo, (2) reenviar
la misma versión, (3) versión posterior, (4) versión antigua tardía, (5) magnitud nula, (6) coordenadas
inválidas, (7) evento marítimo, (8) reiniciar consumidor, (9) cerrar el túnel, (10) reabrir el túnel,
(11) reproducción histórica. Entregables de §12: ver `matrix-12-13.md`.

## Decisión R5 (T003): medir la API con 1.000.000 de filas sin tocar `api/`

La API fija el esquema por modo (`api/app/db.py`: `SEARCH_PATHS = {"live": "core", "replay": "replay, core"}`).
No puede leer `bench` sin cambiar el código. **Decisión: no se modifica `api/`.** El script de medición
(en `tests/benchmark/`) importa la aplicación en proceso dentro del contenedor `tests`, sustituye en memoria
`SEARCH_PATHS["replay"]` por `"bench, core"`, y consulta el modo `replay` sobre el esquema sintético
`bench` (que se crea, se concede a la API en solo lectura y se elimina al terminar). Es una medición en
proceso (sin red ni túnel), igual que la de la 006, y se declara como tal. No es un cambio del contrato.
