# Guía de validación (008)

Cada escenario se ejecuta con la skill `verify-stack` y deja esperado/observado en
`docs/evidence/008/`. Nada se da por superado sin esa evidencia.

**Requisitos**: stack levantado (`docker compose up --build -d`), catálogo de 2025 cargado, sin
tocar `.env`. Compose: `docker compose -f compose.yaml -f compose.dev.yaml`.

| # | Escenario | Orden / acción | Esperado |
|---|---|---|---|
| V1 | Conclusiones regenerables | Ejecutar las consultas de `tests/analysis` y las llamadas a la API de cada conclusión | Cada cifra coincide con la memoria (o difiere según el instante anotado) |
| V2 | Comparación equivalente | Últimas 24 h con `min_mag=4` frente a media diaria de 2025 con `min_mag=4` | Mismo filtro en ambos; denominador 365; razón distinta de 3,87 y explicada |
| V3 | Capturas | Abrir el panel con los filtros de cada conclusión | Captura con periodo, filtros, unidad y sin valor visibles |
| V4 | Exclusión de sintéticos y reproducción | Contar eventos en `core.event_current` con y sin los casos sintéticos | Las cifras reales no los incluyen |
| V5 | Estructuras | `run --rm tests python -m tests.benchmark.structure_benchmark` con 3 tamaños | Tabla de tiempo y pico de memoria por variante y tamaño; diccionario y consulta indexada no crecen linealmente |
| V6 | API con 1.000.000 | `api_latency.py` sobre datos sintéticos aislados | Medianas ≤ 2.000 ms o límite alcanzado documentado; `bench` eliminado después |
| V7 | Aislamiento | Tras V6, comprobar que `core` no cambió y `bench` no existe | Recuentos de `core` idénticos; sin esquema `bench` |
| V8 | Costes | Revisar cada cifra del informe | Cada cifra es medida con enlace o supuesto con valor y fuente; ningún beneficio sin definir |
| V9 | Matrices | Abrir todos los enlaces de las matrices §11, §12, §13 | 0 enlaces rotos; 11 pruebas con estado y hueco |
| V10 | Coherencia de `report.md` | Comprobar índice, enlaces y cifras repetidas | Enlaces resuelven; cifras iguales entre secciones |
| V11 | Higiene | `git ls-files` frente a patrones de `node_modules`, secretos, volúmenes, datos | 0 hallazgos o hallazgo documentado |
| V12 | Huecos de la usuaria | Revisar los procedimientos de Linux (002, 003, 005, 006) y otro dispositivo | Cada hueco tiene procedimiento y ruta de evidencia, no figura como superado |

Las pruebas pytest de los scripts de medición se ejecutan una sola vez, sin concurrencia con
`tests/db`.
