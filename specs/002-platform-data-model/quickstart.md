# Quickstart: validar la plataforma y el modelo

Guía para comprobar la funcionalidad de extremo a extremo una vez implementada. Cada escenario
indica la historia de usuario y el criterio de éxito que evidencia. Los resultados observados se
guardan en `docs/evidence/002/`.

Referencias: [data-model.md](data-model.md), [contracts/database.md](contracts/database.md),
[contracts/runtime.md](contracts/runtime.md).

## Requisitos

- Docker Engine 26 o posterior con Compose v2.
- Un `.env` creado desde `.env.example` con contraseñas locales.
- Si existe un volumen del modelo anterior, recrearlo. **Esto borra la base local**:

  ```bash
  docker compose down -v
  ```

## V1. Arranque desde cero (US1 · SC-001, SC-002)

```bash
docker compose up --build -d
docker compose ps
```

Esperado: cinco servicios (`postgres`, `kafka`, `producer`, `consumer`, `api`) en estado
`healthy` en menos de tres minutos con las imágenes ya construidas; ningún servicio `tunnel`.
Repetir diez veces con `docker compose down -v` entre medias y anotar el tiempo de cada
arranque.

## V2. Superficie expuesta (US1 · SC-008)

```bash
docker compose ps --format '{{.Service}} {{.Ports}}'
```

Esperado: solo `api` publica un puerto, y lo hace en `127.0.0.1:8000`. Desde otro dispositivo de
la red, los puertos 5432, 9092 y 8000 del equipo no responden.

## V3. Estructura creada sin pasos manuales (US1, US3)

```bash
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\dt core.*' -c '\dt replay.*'
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc \
  "select count(*) from core.dim_country; select min(date_id), max(date_id), count(*) from core.dim_date;"
```

Esperado: las tablas de [data-model.md](data-model.md) en `core`; las seis tablas de eventos en
`replay`; 177 países; fechas de 1900-01-01 a 2035-12-31 sin huecos (49.673 filas).

## V4. Secuencia de duplicados y revisiones (US2 · SC-003)

Ejecutar la prueba automática del modelo, que aplica la secuencia de la FAQ 12 sobre una base
temporal:

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests pytest tests/db -v
```

Esperado: resultados `new`, `duplicate`, `revised`, `duplicate`, `new`; 2 eventos actuales, 3
versiones, 5 mensajes registrados, E1 con la magnitud revisada. La misma prueba cubre magnitud y profundidad nulas,
profundidad negativa aceptada, evento sin país y coordenadas fuera de rango rechazadas.

## V5. Idempotencia masiva (US2 · SC-004)

Incluida en `tests/db`: reaplicar 1.000 veces el mismo conjunto de versiones y comparar
recuentos de eventos, versiones y cuarentena antes y después. Esperado: idénticos.

## V6. Aislamiento de la reproducción (US3 · SC-005)

Incluida en `tests/db`: insertar 10.000 eventos en `replay` con identificadores que también
existen en `core`, vaciar `replay` y comparar un resumen de `core` (recuento y suma de
comprobación) antes y después. Esperado: idéntico.

## V7. Privilegios (R12)

```bash
docker compose exec postgres psql -U observatory_reader -d "$POSTGRES_DB" -c "delete from core.event_current"
```

Esperado: `permission denied`.

## V8. Persistencia tras reinicio (US1)

```bash
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select count(*) from core.event_current"
docker compose down && docker compose up -d
```

Esperado: el mismo recuento después de reiniciar, y el productor no vuelve a publicar versiones
ya publicadas. Tras un arranque desde cero, todo `event_id` de
`core.publish_state` aparece en `core.message_log`: el consumidor no ha perdido los mensajes
publicados antes de unirse al grupo.

## V9. Reintentos (US1)

```bash
docker compose stop postgres && sleep 30 && docker compose start postgres
docker compose logs --since 2m consumer producer api
```

Esperado: avisos de reintento con espera creciente y recuperación sin reiniciar manualmente
ningún servicio; `/api/salud` informa de estado degradado mientras dura la caída.

## V10. Túnel opcional (US1 · FR-007)

```bash
docker compose --profile tunnel up -d
```

Esperado: con `NGROK_AUTHTOKEN` y `NGROK_DOMAIN` en `.env`, la URL HTTPS responde en
`/api/salud`. Sin ellos, los cinco servicios obligatorios siguen sanos.

## V11. Medición de índices (US5 · SC-007)

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m tests.benchmark.index_benchmark
```

Esperado: tabla con tiempo sin y con cada índice candidato para 10.000, 100.000 y 1.000.000 de
filas sintéticas en el esquema `bench`, y el esquema eliminado al terminar. Anotar equipo y
fecha. Se conservan los índices cuya consulta es al menos 2 veces más rápida en mediana en el
tamaño mayor; el resto se retira del SQL y se documenta.

## V12. Higiene del repositorio (US1 · SC-009)

```bash
git ls-files -z | xargs -0 du -k | awk '$1 > 5000'
git ls-files | grep -E '(^|/)\.env$|node_modules/' || echo "limpio"
```

Esperado: solo aparece `frontend/public/datos/paises.geojson` si supera el umbral; ninguna
credencial ni `node_modules`.

## Recrear la base desde cero

Los ficheros de inicialización solo se ejecutan con el volumen vacío. Para aplicar un cambio de
modelo en desarrollo: `docker compose down -v` y volver a arrancar. La carga histórica se repite
con el procedimiento de la spec 003.
