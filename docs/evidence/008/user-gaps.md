# Huecos que ejecuta la usuaria (T027)

Comprobaciones que necesitan otro equipo, otro dispositivo u otra persona. **Ninguna pendiente figura como superada**: cada una tiene su
procedimiento y su ruta de evidencia. G4 se ejecutó el 2026-11-17. Cada procedimiento se puede hacer en menos de 30 minutos.

| Id | Hueco | Origen | Dónde |
|---|---|---|---|
| G1 | Puertos 5432, 9092 y 8000 cerrados desde otro dispositivo de la red | 002 V2 (SC-008) | otro dispositivo en la misma red |
| G2 | Arranque desde cero por una persona ajena al proyecto, solo con `README.md` | 002 T057 (SC-001) | otra persona |
| G3 | Pruebas en Linux de las specs 002, 003, 005 y 006 | 002, 003 T050, 005, 006 | equipo Linux |
| G4 | Panel desde otro dispositivo físico (túnel y Netlify) | 007; §11 pruebas 9 y 10 | **HECHO el 2026-11-17** (móvil con datos móviles; [007 M1 a M3](../007/README.md)) |

## G1 · Puertos cerrados desde otro dispositivo (002 V2)

1. En el equipo del stack: `docker compose up -d` y `ipconfig` (Windows) o `ip addr` (Linux) para anotar su IP de red local, `IP`.
2. Desde el otro dispositivo (móvil con una app de escaneo de puertos, u otro portátil con `nc -vz IP 5432`, `9092` y `8000`).
3. **Esperado**: los tres puertos rechazan o no responden (la API solo escucha en `127.0.0.1:8000`).
4. Registrar fecha, dispositivo, orden y salida en la fila V2 de [docs/evidence/002/README.md](../002/README.md) y marcarla superada.

## G2 · Arranque por una persona ajena (002 T057)

1. Dar a otra persona el repositorio y que arranque el sistema solo con `README.md` (copiar `.env.example` a `.env`,
   `docker compose up --build -d`).
2. Anotar el tiempo hasta que `docker compose ps` muestra los servicios en `healthy` y cualquier duda o paso que no estuviera claro.
3. **Esperado**: el sistema arranca en menos de 3 minutos con imágenes ya descargadas, sin pasos no documentados.
4. Registrar en [docs/evidence/002/README.md](../002/README.md) y marcar T057.

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
