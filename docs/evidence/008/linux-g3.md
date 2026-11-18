# G3 · Pruebas en Linux (specs 002, 003, 005 y 006)

**Fecha**: 2026-11-17 · **Rama**: `008-analysis-costs-deliverables` · Ejecutadas por la persona autora; las salidas son capturas de su terminal, transcritas aquí.
**Equipo**: Intel Core i5-10600 @ 3,30 GHz, 12 núcleos lógicos, 7,6 GiB de RAM, Linux 6.12.51 (según la cabecera que imprime `api_latency.py`).

## 1. Suite completa en el contenedor `tests`

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m pytest tests -q
```

**Esperado**: toda la suite en verde, una sola ejecución. **Observado**: `886 passed in 1604.34s (0:26:44)` ([captura](linux-pytest.png)). **Resultado: SUPERADA.**
La suite incluye las pruebas de las specs 002 a 008 (con `tests/db`, así que ejerce el modelo, las funciones de versiones y el aislamiento con una base de Linux).

## 2. Latencia de la API (`tests/benchmark/api_latency.py`)

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python3 tests/benchmark/api_latency.py --base-url http://api:8000
```

**Observado** ([captura](linux-api-latency.png)): modo `replay`, **0 eventos de 2025**; pequeña 1,7 ms, página completa 1,7 ms y estadísticas 22,6 ms de mediana; `SC-008 ... PASS`.

**Resultado: NO CONCLUYENTE.** La base de Linux está vacía de datos de 2025 (el volumen de Docker es local a cada equipo), así que el PASS es trivial: mide consultas sobre cero filas, no la latencia
real. Para que valga habría que cargar 2025 en el Linux (`catalog-loader`, ver `README.md`) y repetir. La latencia con datos se midió en Windows ([006 v16](../006/v16-latency.md)) y con 1.000.000 de filas ([api-latency-1m.md](api-latency-1m.md)).

## 3. Arranque del stack

```bash
docker compose up --build -d --wait
```

**Esperado**: los cinco servicios obligatorios en `healthy`. **Observado** ([captura](linux-up.png)): `postgres`, `kafka`, `api`, `producer` y `consumer` en `Healthy` (15,8 s, 15,8 s, 19,0 s, 30,0 s y 30,0 s), con los volúmenes y la red
creados en esa misma ejecución (base de Linux nueva). **Resultado: SUPERADA.**

## 4. Alcance

Se ejecutaron en Linux la suite completa, el arranque y la medición de latencia (esta no concluyente). Quedaron fuera, por decisión de la persona autora y por no ser requisito del enunciado, la comprobación de
propiedad de ficheros de la carga del catálogo (003 T050) y la repetición de los escenarios con el sistema real de las specs 005 y 006. Lo que aporta esta evidencia: el código y las pruebas automáticas
de las specs 002 a 008 se comportan igual en Linux que en Windows (886 pruebas en verde) y el stack arranca sano desde cero.
