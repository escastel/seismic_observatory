# Entorno de la verificación

**Fecha**: 2026-11-16 · **Rama**: `005-historical-replay` · **Equipo**: Windows 11 Pro, Git Bash,
Docker Desktop (motor 29.1.3) · **Compose**: `docker compose up --build -d` desde el árbol de trabajo.

## Servicios al empezar (`docker compose ps`)

| Servicio | Estado |
|---|---|
| postgres, kafka, consumer, producer, api | `healthy` |
| replay | perfil `tools`: no arranca con `up`; se ejecuta con `docker compose run --rm replay …` |

## Datos de partida

- Catálogo USGS de 2025 con magnitud ≥ 4 ya descargado y registrado por la spec 003:
  28 ficheros en `data/usgs/catalog/` (ignorado por Git). No se volvió a consultar a USGS en ningún
  momento de la verificación.
- `core` con 34.037 eventos actuales y 34.196 versiones al tomar la instantánea (ver
  [v2-v3-replay-5000.out](v2-v3-replay-5000.out)).
- Grupo del consumidor en Kafka: `observatorio-consumer` (valor del `.env` local, que no se lee ni se
  imprime).

## Procedimiento común

1. Productor en vivo parado (`docker compose stop producer`) mientras dura la comprobación de
   aislamiento, porque el feed real escribe en `core` por su cuenta. Se reanudó al terminar V7
   (`docker compose start producer`).
2. Antes de cada comparación se esperó a que el consumidor estuviera al día en el topic de
   reproducción (retraso 0 en `kafka-consumer-groups --describe`).
3. Las consultas SQL están en [sql/](sql/) y se ejecutan con
   `docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < fichero.sql`
   (las credenciales las lee el contenedor de su propio entorno).
4. Las órdenes de reproducción usan el servicio `replay` de Compose (contrato
   [replay-cli.md](../../../specs/005-historical-replay/contracts/replay-cli.md)).

## Limitaciones declaradas

- Medidas hechas en un solo equipo, sin repetir en Linux (la usuaria alterna entre ambos; lo
  hecho aquí es el flujo de Docker, que es el mismo, pero no se ha ejecutado en el equipo Linux).
- Durante la verificación, una prueba de la spec 004
  (`tests/unit/test_synthetic_cases.py::…[model_constraint_violation]`) fallaba en el equipo Windows
  fuera de Docker y pasaba en el contenedor Linux, con o sin los cambios de esta spec. Se corrigió
  después (ver el hallazgo 2 del [README](README.md)); las cifras de este documento son anteriores y no
  cambian.
