# Huecos que ejecuta la usuaria (T027)

Comprobaciones que necesitan otro equipo, otro dispositivo u otra persona. **Ninguna pendiente figura como superada**: cada una tiene su
procedimiento y su ruta de evidencia. G4 se ejecutó el 2026-11-17 con capturas. G1 (puertos cerrados desde otro dispositivo) y G2 (arranque por una persona ajena) se retiraron de este seguimiento a petición de la usuaria; la fila V2 y la tarea T057 de la spec 002 siguen constando como pendientes en `docs/evidence/002/README.md`. Cada procedimiento se puede hacer en menos de 30 minutos.

| Id | Hueco | Origen | Dónde |
|---|---|---|---|
| G3 | Pruebas en Linux de las specs 002, 003, 005 y 006 | 002, 003 T050, 005, 006 | **PARCIAL el 2026-11-17**: suite completa 886 pruebas en verde ([linux-g3.md](linux-g3.md)); falta la salida de T050 (`ls -ln`) y la de `up --wait`; la latencia salió con 0 eventos (no concluyente) |
| G4 | Panel desde otro dispositivo físico (túnel y Netlify) | 007; §11 pruebas 9 y 10 | **HECHO el 2026-11-17** (móvil con datos móviles; [007 M1 a M3](../007/README.md)) |

## G3 · Linux (specs 002, 003, 005, 006)

En el equipo Linux, con el repositorio actualizado (`git fetch` y comparar con `origin/main` antes de `git pull`):

```bash
docker compose up --build -d --wait
LOADER_UID=$(id -u) LOADER_GID=$(id -g) docker compose run --rm catalog-loader --dry-run
LOADER_UID=$(id -u) LOADER_GID=$(id -g) docker compose run --rm catalog-loader --start 2025-01-01 --end 2025-01-02
ls -ln data/usgs/catalog | tail -3         # propietario: el uid propio, no 0   (003 T050)
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m pytest tests -q   # una sola ejecución
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python3 tests/benchmark/api_latency.py --base-url http://api:8000
```

- **Esperado**: servicios `healthy`; ficheros de `data/` propiedad del usuario; suite en verde; latencia con la misma forma que en
  [006 v16](../006/v16-latency.md) (medianas por debajo de 2.000 ms).
- Si el volumen de PostgreSQL es anterior a la spec 004, aplicar la migración (sección «Base creada antes de la spec 004» de
  `README.md`).
- Los volúmenes de Docker son locales: el estado de la base de un equipo no dice nada del otro.
- Registrar la salida en `docs/evidence/002`, `003`, `005` y `006` (una nota «Linux» en cada README) y marcar T050 de la 003.
- Añadir los resultados de rendimiento de [008](structure-benchmark.md) en Linux (misma orden, otro equipo) si se quieren comparar.

## G4 · Panel desde otro dispositivo físico (007; §11 pruebas 9 y 10) — HECHO el 2026-11-17 ([007 M1 a M3](../007/README.md))

1. Levantar el stack y el túnel (`docker compose --profile tunnel up -d` o el agente de ngrok en el host).
2. Abrir la URL de Netlify en el móvil con datos móviles (otra red).
3. **Esperado**: el panel carga mapa, gráficos y tabla con datos de las últimas 24 h y el estado «Datos al día».
4. Parar el túnel; **esperado**: en el siguiente refresco (≤ 60 s) aviso de backend inaccesible conservando la última lectura
   identificada como tal. Reabrir el túnel; **esperado**: recuperación sin recargar en ≤ 60 s.
5. Guardar capturas en `docs/evidence/007/` y completar la sección «Sigue sin probarse» de su README.
