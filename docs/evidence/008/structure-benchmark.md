# Medición de estructuras de datos (spec 008)

> **SINTÉTICO**: todos los datos de esta medición son generados con semilla fija; no son datos del observatorio y no se han cargado en `core` ni en `replay`.

- Fecha (UTC): 2026-11-17T14:56:35Z
- Servidor: PostgreSQL 16.4 (Debian 16.4-1.pgdg120+2) on x86_64-pc-linux-gnu, compiled by gcc (Debian 12.2.0-14) 12.2.0, 64-bit; shared_buffers 128MB, work_mem 4MB
- Cliente: Linux 6.18.58.1-microsoft-standard-WSL2 x86_64, Python 3.11.10; CPU 11th Gen Intel(R) Core(TM) i5-11400H @ 2.70GHz; 12 CPU y 7.6 GiB visibles en el contenedor
- Versiones: shapely 2.0.6, geopandas 1.0.1, numpy 2.4.6, psycopg 3.2.3, python 3.11.10
- Orden: `docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m tests.benchmark.structure_benchmark`

## Procedimiento

1. Se crea el esquema `bench` con tablas propias (no toca `core` ni `replay`) y se elimina al terminar, también si la medición falla. Tamaños: 10.000, 100.000, 1.000.000; semilla 20250101.
2. Tiempo: mediana de 5 repeticiones tras 1 de calentamiento con `time.perf_counter`. Las variantes más lentas llevan menos repeticiones: como mucho 3 desde 100.000 filas y 1 (sin calentamiento) el bucle ingenuo de polígonos con 1.000.000 de puntos; la columna «Repeticiones» lo indica.
3. Memoria: pico de `tracemalloc` al construir la estructura y ejecutar la operación una vez; solo ve la memoria de Python y NumPy, no la de GEOS ni la de PostgreSQL (`—`). No se mide para el bucle ingenuo con 1.000.000 de puntos.
4. Búsqueda: 100 identificadores al azar más uno inexistente sobre versiones (5 % de los eventos con dos). Las variantes Python miden la búsqueda; la construcción del diccionario se da en «Construcción».
5. Geografía: puntos uniformes en longitud y latitud contra los polígonos de `frontend/public/datos/paises.geojson` (Natural Earth), con el orden y la regla del consumidor (por `ADM0_A3`, gana el primero que intersecta). El tiempo del STRtree incluye consultar, no construir el árbol (se da en «Construcción»).
6. Agregación por hora UTC: 2025 con eventos a segundos aleatorios; Python recorre `datetime` con diccionario; SQL usa `date_bin('1 hour', ...)`. En SQL el tiempo incluye traer el resultado.
7. Todas las variantes de una operación deben devolver el mismo resultado; la columna «Idéntico» lo comprueba.

## `search`

### 10.000 filas: Versiones de 101 identificadores (uno inexistente) entre 10.500 versiones

| Variante | Mediana (ms) | Repeticiones | Construcción (ms) | Pico Python (KiB) | Idéntico | Plan |
|---|---:|---:|---:|---:|:--:|---|
| lista, búsqueda secuencial | 17,987 | 5 | 0,1 | 89 | sí | — |
| diccionario por event_id | 0,008 | 5 | 1,4 | 1.059 | sí | — |
| SQL sin clave primaria | 67,480 | 5 | 0,0 | — | sí | Sort → Seq Scan |
| SQL con clave primaria (event_id, updated_s) | 11,126 | 5 | 0,0 | — | sí | Index Scan using versions_pk_pkey |

### 100.000 filas: Versiones de 101 identificadores (uno inexistente) entre 105.000 versiones

| Variante | Mediana (ms) | Repeticiones | Construcción (ms) | Pico Python (KiB) | Idéntico | Plan |
|---|---:|---:|---:|---:|:--:|---|
| lista, búsqueda secuencial | 362,378 | 3 | 1,3 | 827 | sí | — |
| diccionario por event_id | 0,008 | 5 | 61,7 | 13.137 | sí | — |
| SQL sin clave primaria | 492,612 | 3 | 0,0 | — | sí | Sort → Seq Scan |
| SQL con clave primaria (event_id, updated_s) | 12,543 | 5 | 0,0 | — | sí | Index Scan using versions_pk_pkey |

### 1.000.000 filas: Versiones de 101 identificadores (uno inexistente) entre 1.050.000 versiones

| Variante | Mediana (ms) | Repeticiones | Construcción (ms) | Pico Python (KiB) | Idéntico | Plan |
|---|---:|---:|---:|---:|:--:|---|
| lista, búsqueda secuencial | 2767,741 | 3 | 14,3 | 8.210 | sí | — |
| diccionario por event_id | 0,008 | 5 | 1047,2 | 115.977 | sí | — |
| SQL sin clave primaria | 2334,576 | 3 | 0,0 | — | sí | Sort → Gather → Seq Scan |
| SQL con clave primaria (event_id, updated_s) | 11,718 | 5 | 0,0 | — | sí | Index Scan using versions_pk_pkey |

## `geo`

### 10.000 filas: País de 10.000 puntos aleatorios entre 177 polígonos de Natural Earth

| Variante | Mediana (ms) | Repeticiones | Construcción (ms) | Pico Python (KiB) | Idéntico | Plan |
|---|---:|---:|---:|---:|:--:|---|
| bucle ingenuo sobre todos los polígonos | 5091,117 | 5 | 1,4 | 782 | sí | — |
| índice espacial STRtree | 19,189 | 5 | 1,2 | 840 | sí | — |

### 100.000 filas: País de 100.000 puntos aleatorios entre 177 polígonos de Natural Earth

| Variante | Mediana (ms) | Repeticiones | Construcción (ms) | Pico Python (KiB) | Idéntico | Plan |
|---|---:|---:|---:|---:|:--:|---|
| bucle ingenuo sobre todos los polígonos | 50319,413 | 3 | 41,3 | 7.813 | sí | — |
| índice espacial STRtree | 194,710 | 5 | 41,1 | 8.338 | sí | — |

### 1.000.000 filas: País de 1.000.000 puntos aleatorios entre 177 polígonos de Natural Earth

| Variante | Mediana (ms) | Repeticiones | Construcción (ms) | Pico Python (KiB) | Idéntico | Plan |
|---|---:|---:|---:|---:|:--:|---|
| bucle ingenuo sobre todos los polígonos | 504088,197 | 1 | 555,7 | — | sí | — |
| índice espacial STRtree | 1836,879 | 5 | 599,7 | 83.747 | sí | — |

## `hourly`

### 10.000 filas: Eventos por hora UTC entre 10.000 eventos de 2025

| Variante | Mediana (ms) | Repeticiones | Construcción (ms) | Pico Python (KiB) | Idéntico | Plan |
|---|---:|---:|---:|---:|:--:|---|
| bucle Python con diccionario | 14,654 | 5 | 0,0 | 1.042 | sí | — |
| SQL GROUP BY con date_bin | 7,410 | 5 | 0,0 | — | sí | Aggregate → Sort → Seq Scan |

### 100.000 filas: Eventos por hora UTC entre 100.000 eventos de 2025

| Variante | Mediana (ms) | Repeticiones | Construcción (ms) | Pico Python (KiB) | Idéntico | Plan |
|---|---:|---:|---:|---:|:--:|---|
| bucle Python con diccionario | 118,673 | 5 | 0,0 | 1.451 | sí | — |
| SQL GROUP BY con date_bin | 34,947 | 5 | 0,0 | — | sí | Aggregate → Sort → Seq Scan |

### 1.000.000 filas: Eventos por hora UTC entre 1.000.000 eventos de 2025

| Variante | Mediana (ms) | Repeticiones | Construcción (ms) | Pico Python (KiB) | Idéntico | Plan |
|---|---:|---:|---:|---:|:--:|---|
| bucle Python con diccionario | 1092,756 | 5 | 0,0 | 1.451 | sí | — |
| SQL GROUP BY con date_bin | 330,688 | 5 | 0,0 | — | sí | Aggregate → Sort → Seq Scan |

