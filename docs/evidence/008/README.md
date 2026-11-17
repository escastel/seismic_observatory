# Evidencias de la spec 008: análisis, rendimiento, costes y cierre

**Fecha**: 2026-11-17 · **Rama**: `008-analysis-costs-deliverables` · **Equipo**: [00-environment.md](00-environment.md) (Windows 11 Pro, i5-11400H,
Docker Desktop 29.1.3, PostgreSQL 16.4). Escenarios de [quickstart.md](../../../specs/008-analysis-costs-deliverables/quickstart.md). Cada fila enlaza con su evidencia;
ninguna se marca superada sin haberse ejecutado.

| Id | Qué comprueba | Esperado | Observado | Estado | Evidencia |
|---|---|---|---|---|---|
| V1 | Conclusiones regenerables | cada cifra coincide con la memoria | 4 conclusiones; SQL y API coinciden en 18.302, 14.350, 16.173/1.984/129/15/1, 15 (día 2026-11-16) | SUPERADA | [analysis-queries.md](analysis-queries.md) |
| V2 | Comparación equivalente | mismo filtro en ambos periodos; razón distinta de 3,87 | `min_mag=4`: 0,28 (24 h) y 0,30 (día completo); sin filtro 3,37 marcada como no equivalente; USGS confirma 14, 15 y 15 para tres días bajos | SUPERADA | [analysis-queries.md](analysis-queries.md) |
| V3 | Capturas con los filtros | periodo, filtros y unidad visibles | 3 capturas: 2025 con `min_mag=4`, 24 h con `min_mag=4` y 24 h sin filtro | SUPERADA | [C1](C1-2025-m4.png), [C2a](C2a-24h-m4.png), [C2b](C2b-24h-nofilter.png), [captures.json](captures.json) |
| V4 | Sintéticos y reproducción fuera | cifras reales sin ellos | día 2026-11-16, M ≥ 4: 516 con sintéticos, 15 sin ellos; la API en modo real da 15; `replay` no participa | SUPERADA | [analysis-queries.md](analysis-queries.md) (T008) |
| V5 | Estructuras con 3 tamaños | tiempo y memoria por variante y tamaño; resultados idénticos | 3 operaciones × 3 tamaños, todos los resultados idénticos; diccionario y clave primaria no crecen con n | SUPERADA | [structure-benchmark.md](structure-benchmark.md), [.json](structure-benchmark.json) |
| V6 | API con 1.000.000 de filas | medianas ≤ 2.000 ms | máxima mediana 1.276,4 ms; 0 fallos; con y sin índices secundarios | SUPERADA | [api-latency-1m.md](api-latency-1m.md) |
| V7 | Aislamiento tras V5 y V6 | `core` y `replay` sin cambios; sin `bench` | 18.302 / 1.013 / 2.807 iguales; 0 esquemas `bench` | SUPERADA | [api-latency-1m.md](api-latency-1m.md) |
| V8 | Costes | cada cifra es medida enlazada o supuesto con valor y fuente; ningún beneficio sin definir | partidas con columna medida/supuesto; ROI «no estimado»; flujos de la evaluación anterior retirados | SUPERADA | [cost-table.md](cost-table.md), [cost-measurements.md](cost-measurements.md), [free-tier-limits.md](free-tier-limits.md) |
| V9 | Matrices | sin enlaces rotos; 11 pruebas con estado y hueco | 11 de 11 con evidencia; huecos de la usuaria en user-gaps.md | SUPERADA | [matrix-11.md](matrix-11.md), [matrix-12-13.md](matrix-12-13.md) |
| V10 | Coherencia de `report.md` | enlaces e índice válidos; cifras iguales | 267 enlaces, 0 rotos; 4 correcciones | SUPERADA | [report-coherence.md](report-coherence.md) |
| V11 | Higiene | 0 hallazgos o hallazgo documentado | 0 en el árbol versionado; 1 hallazgo en el historial local (rama `backup/main-before-fix`), resuelto al borrar la rama con confirmación | SUPERADA | [repository-hygiene.md](repository-hygiene.md) |
| V12 | Huecos de la usuaria | procedimiento y ruta de evidencia | G3 y G4 con procedimiento; **G4 ejecutado el 2026-11-17** (móvil con datos móviles, [007 M1 a M3](../007/README.md)); G3 (Linux) en ejecución por la usuaria; G1 y G2 retirados del seguimiento a petición de la usuaria | **PARCIAL: G3 en curso** | [user-gaps.md](user-gaps.md) |

Pruebas automáticas del código de medición: `pytest tests/benchmark` → 5 pasan ([tests.txt](tests.txt)); no se tocó nada de `db/`, así que no se repitió `tests/db`.

## Cambios fuera del alcance previsto

- Ninguno en `api/`, `frontend/` ni `db/`. La medición con 1.000.000 de filas importa la API en proceso y sustituye `SEARCH_PATHS["replay"]` solo en memoria.
- `frontend/public/config.json` se cambió temporalmente a la API local para las capturas y se restauró (`git diff` vacío).
