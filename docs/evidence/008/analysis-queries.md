# Consultas del análisis y contraste con la API (T005–T008)

**Ejecución**: 2026-11-17 14:34–14:35 UTC · **Rama**: `008-analysis-costs-deliverables` · **Datos**: esquema
`core` (real), PostgreSQL 16.4 y API en marcha en el equipo descrito en [00-environment.md](00-environment.md).
Las consultas están en [tests/analysis/queries.sql](../../../tests/analysis/queries.sql); la salida literal en
[analysis-queries.out](analysis-queries.out). Filtro común: `event_id NOT LIKE 'synthetic-%'` y, salvo en Q0, Q1 y
Q3c, magnitud ≥ 4. Periodos en UTC, inicio inclusivo, fin exclusivo.

## T005 · Resultados

| Consulta | Qué mide | Resultado observado |
|---|---|---|
| Q0 | Eventos reales por año | 2025: 18.302 · 2026 (hasta 17-nov): 14.893 · sin magnitud ni profundidad nulas en ambos años |
| Q1 | Cobertura de 2025 | 18.302 eventos, todos con magnitud ≥ 4 (mínimo 4,0): el catálogo cargado no contiene M < 4 |
| Q2 | País, 2025, M ≥ 4 | **Sin país asignado 14.350 (78,4 %)**; China 354 (1,9 %), Chile 348, Indonesia 306, Etiopía 265, Argentina 236 |
| Q2b | Sin país por tramo de magnitud | 4–5: 77,6 % · 5–6: 84,8 % · 6–7: 84,5 % · 7–8: 80,0 % · 8–9: 100 % (1 evento) |
| Q3 | Media diaria 2025, M ≥ 4 | 365 días, **0 días sin eventos**, 18.302 eventos, media 50,14 eventos/día |
| Q3b | Periodos recientes, M ≥ 4 | día 2026-11-16 completo: **15** · catálogo 2026-01-01..11-15 (319 días): 14.225 |
| Q3c | Comparación no equivalente | 2026-11-16 con todas las magnitudes: 200 eventos, de ellos 15 con M ≥ 4 |
| Q3d | Distribución de eventos/día, M ≥ 4 | 2025: media 50,14, mediana 43, desv. 41,13, mín. 20, p05 27, p95 89, máx. 645, 0 días ≤ 15 · 2026-01-01..11-14: media 44,73, mediana 41, mín. 14, 2 días ≤ 15 |
| Q4 | Hora UTC, 2025, M ≥ 4 | de 681 (15 h) a 832 (03 h) eventos por hora; media 762,6 |
| Q5 | Profundidad por subregión | medianas: Sudamérica 117,1 km, Melanesia 86,1, Europa del Este 52,3, Asia oriental 10,0, Sin país asignado 22,0 |
| Q6 | Tipos de magnitud | catálogo 2025 M ≥ 4: mb 16.332 (89,2 %), mww 1.476, mwr 354, ml 76, mw 29, md 29, mwb 6 · feed 10–17 nov todas las magnitudes: ml 384, md 145, mb 131, mww 25 |
| Q7 | Profundidad fijada | **8.258 de 18.302 (45,1 %) con profundidad exactamente 10 km** (valor habitual de profundidad no determinada); 0 profundidades negativas |
| Q8 | Uniformidad horaria | máximo/mínimo 1,22; χ² = 41,1 con 23 grados de libertad |

## T006 · Contraste con `GET /api/estadisticas` (mismo periodo y filtros)

| Cifra | SQL | API | Coincide |
|---|---|---|---|
| Total 2025, `min_mag=4` | 18.302 | 18.302 | sí |
| Sin país asignado 2025 | 14.350 | 14.350 | sí |
| Magnitud 4–5, 5–6, 6–7, 7–8, 8–9 | 16.173 / 1.984 / 129 / 15 / 1 (Q2b) | 16.173 / 1.984 / 129 / 15 / 1 | sí |
| Profundidad 0–70, 70–300, ≥ 300 km | — | 13.689 / 3.511 / 1.102 (suman 18.302) | coherente con Q7 |
| Día 2026-11-16, `min_mag=4` | 15 | 15 (`start=2026-11-16T00:00:00Z&end=2026-11-17T00:00:00Z`) | sí |
| Razón día 2026-11-16 / media 2025 | 15 / 50,14 | 0,299 | sí |

Llamadas de las últimas 24 h (ventana por defecto, 14:34:43 UTC): con `min_mag=4` → **14 eventos**, razón **0,279**
(media 50,14); **sin filtro** → 169 eventos, razón **3,370** (la «razón 3,87» del panel fue la misma comparación no
equivalente a otra hora). De los 169, 155 son M < 4 y 131 son de Estados Unidos.

## T007 · Comparación equivalente frente a la que no lo es

| | Periodo reciente | Eventos | Media diaria de 2025 | Razón | Equivalente |
|---|---|---:|---|---:|---|
| Sin filtro (la del panel) | últimas 24 h | 169 | 50,14 (solo M ≥ 4) | 3,37 | **No**: el feed incluye todas las magnitudes y 2025 solo M ≥ 4 |
| `min_mag=4` | últimas 24 h | 14 | 50,14 | 0,28 | Sí |
| `min_mag=4` | día completo 2026-11-16 | 15 | 50,14 | 0,30 | Sí, con periodo cerrado |

Denominador: 365 días incluidos los de cero (hay 0 días con cero en 2025 con M ≥ 4, por lo que el
resultado no cambia, pero la regla se aplica y se declara). Una media 0 daría ND.

Comprobación de que el valor bajo no es un hueco de carga: la API `count` de USGS (`eventtype=earthquake`,
`minmagnitude=4`, día UTC completo, consultada el 2026-11-17 14:36 UTC) devuelve 14 para 2026-11-04, 15 para
2026-11-08, 15 para 2026-11-16 y 34 para 2026-10-15; nuestra base tiene 14, 15, 15 y 34.

## T008 · Exclusión de sintéticos y de reproducción

| Comprobación | Observado |
|---|---|
| Eventos de `core.event_current` con `synthetic-%` | 1.013, todos en noviembre de 2026 (0 en 2025) |
| 2026-11-16, M ≥ 4, **incluyendo** sintéticos | 516 |
| 2026-11-16, M ≥ 4, **excluyéndolos** (SQL) | 15 |
| 2026-11-16, M ≥ 4, API modo `live` | 15 (la API los excluye por defecto en modo real) |
| `replay.event_current` | 2.807 eventos, no participan en ninguna consulta de `queries.sql` (todas leen `core`) |
| Esquema `bench` | no existe antes ni después de las consultas de esta tarea |

**Resultado**: SUPERADAS T005–T008. Pendiente T009 (capturas del panel).
