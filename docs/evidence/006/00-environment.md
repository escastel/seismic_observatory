# Entorno de la verificación (spec 006)

**Fecha**: 2026-11-16 · **Rama**: `006-query-api` · **Equipo**: Windows 11 Pro for Workstations,
Git Bash, Intel Core i5-11400H (2,70 GHz), 15,7 GB de RAM, Docker Desktop (motor 29.1.3) ·
**Compose**: `docker compose up --build -d` desde el árbol de trabajo.

## Comprobación del esquema (T001)

`quarantine.reason_codes` es `text[] NOT NULL` y `quarantine.is_synthetic` es `boolean`
(`db/sql/040_event_tables.sql`); `event_current.quality_flags` es `text[]`. Las consultas de R5 del
plan son válidas sin cambios de modelo.

## Datos de partida (consulta directa a la base local, solo lectura)

| Dato | Valor |
|---|---|
| `core.event_current` | 34.045 eventos, de 2025-01-01 a 2026-11-16 |
| de ellos con identificador `synthetic-%` | **1.013** |
| `replay.event_current` | 5.301 eventos |
| consultas correctas al feed en `core.extraction` (`ok` o `not_modified`) | 444 |
| última consulta correcta al feed | 2026-11-16 18:41:00 UTC |

**Hallazgo**: el esquema real local contiene 1.013 eventos sintéticos (restos de las pruebas de
escala de la spec 002). Confirma que el filtro defensivo de sintéticos del modo real (plan R2) es
necesario: la API no puede suponer que `core` no los tiene.
