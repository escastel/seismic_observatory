# Quickstart: validar el consumidor y la calidad

Los resultados se guardan en `docs/evidence/004/` con la skill `verify-stack`. Referencias:
[data-model.md](data-model.md), [contracts/rules-catalog.md](contracts/rules-catalog.md),
[contracts/reprocess.md](contracts/reprocess.md).

## Requisitos

- Sistema de las specs 002 y 003 levantado, con 2025 y 2026 cargados.
- Aplicado a la base existente el cambio de modelo de `db/sql/041_consumer_quality.sql` (sin
  recrear el volumen): ver tarea correspondiente.
- SQL dentro del contenedor:
  `docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'`.

## V1. Cada regla a su destino (US1 · SC-001, SC-002)

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests pytest tests/unit/test_rules.py tests/db/test_consumer_rules.py -v
```

Esperado: cada caso de la tabla del catálogo acaba donde dice (cuarentena con todos sus motivos,
exclusión, evento con marcas o evento sin marcas); magnitud nula, negativa, profundidad negativa y
evento de más de 7 días: 0 en cuarentena.

## V2. Pruebas de aceptación con el sistema real (§11)

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m tests.synthetic.inject
```

Esperado, tras unos segundos, en `core`:

| Caso | Resultado |
|---|---|
| Magnitud nula | `event_current` con `magnitude IS NULL`, sin cuarentena |
| Coordenadas inválidas | Fila de cuarentena `coordinates_out_of_range`, sin evento |
| Evento marítimo | `event_current` con `country_id IS NULL` |
| Varios motivos | Una fila de cuarentena con todos los códigos |
| Profundidad negativa | Marca `negative_depth` |

Repetir la inyección: ningún recuento cambia (SC-008, FR-026).

## V3. Reiniciar el consumidor (SC-006)

Publicar 1.000 mensajes sintéticos válidos, reiniciar el consumidor a mitad
(`docker compose restart consumer`) y comparar los recuentos con una ejecución sin reinicio.

## V4. Reprocesado (US2 · SC-003)

```bash
docker compose run --rm quality-reprocess --dry-run
docker compose run --rm quality-reprocess
docker compose run --rm quality-reprocess
```

Esperado: las 2 filas reales de `magnitude_out_of_range` pasan a `recovered_*`; las de coordenadas
inválidas siguen `still_rejected`; la segunda ejecución no cambia nada; `message_log` tiene las
filas `attempt = 1` y conserva las `attempt = 0`.

## V5. País (US3 · SC-004, SC-005)

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests pytest tests/unit/test_spatial.py -v
```

Esperado: interior, océano, frontera y determinismo; catálogo con identificador repetido hace
fallar el arranque con mensaje claro.

## V6. Recuentos (US4 · SC-007)

```bash
docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /queries/quality.sql'
```

Esperado: recibidos = nuevos + revisados + atrasados + repetidos + excluidos + rechazados con
diferencia 0, y recuentos por motivo y por marca con su denominador.

## V7. Sintéticos aparte (US5 · SC-008)

Las consultas de análisis real no devuelven ninguna fila `synthetic`; la variante «solo
sintéticos» las cuenta.

## V8. Calidad en la memoria (US6 · SC-009)

Repetir cada consulta del apartado «Calidad de los datos» de `docs/report.md` y comparar con su
resultado (las cifras que crecen con el feed llevan fecha).

## V9. Nada fuera de alcance (FR-032)

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm tests pytest tests/db tests/unit tests/contract -q
git diff 003-usgs-ingestion --stat -- producer api frontend
```

Esperado: todo en verde; sin cambios en productor, API ni panel.
