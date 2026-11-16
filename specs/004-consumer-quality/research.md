# Research: Consumidor y calidad de los datos

**Fecha**: 2026-11-16 · **Spec**: [spec.md](spec.md)

Sin marcadores NEEDS CLARIFICATION. Las decisiones de la sesión de clarificación (rechazo por el
modelo, reprocesado y sintéticos) están ya en la especificación. **Verificado** el 2026-11-16 en
el sistema real y en el código de las specs 002 y 003.

## Estado de partida (verificado)

| Hecho | Observación |
|---|---|
| Cuarentena real | 2 filas, ambas `magnitude_out_of_range`, ninguna sintética |
| Estado actual | 32.844 eventos; 0 con magnitud nula; 3 con profundidad negativa sin marca; 0 con marcas; 25.335 sin país (el 77 %, porque el catálogo de 2025 y 2026 trae muchos eventos marinos) |
| Registro de mensajes | `new` 32.844, `revised` 97, `quarantined` 2 |
| Reglas heredadas que contradicen la constitución | magnitud nula a cuarentena; rango 0–10; eventos del feed de más de 7 días; tiempo futuro; `duplicate_id` (este último nunca se activaba: `seen_ids` no se pasaba) |
| Asignación de país actual | `matches.iloc[0]`: el orden de los polígonos decide el país en una frontera, no una regla |

## R1. Catálogo de reglas como única fuente

- **Decisión**: un módulo `consumer/app/rules.py` define cada regla como dato (código, dimensión,
  efecto, descripción) y la lógica que la aplica. El catálogo documentado
  ([contracts/rules-catalog.md](contracts/rules-catalog.md)) se genera a la vista del módulo y una
  prueba comprueba que ambos coinciden (código a código).
- **Razón**: FR-001; una regla sin código estable no se puede contar ni citar en la memoria.
- **Alternativas**: reglas dispersas en `if` sin catálogo (lo heredado); catálogo solo en la
  documentación (se desfasa).

## R2. Efectos de una regla y flujo de decisión

Cuatro efectos, en este orden de gravedad:

1. **Cuarentena**: el mensaje no puede tratarse (FR-002). Una sola fila con todos los motivos.
2. **Exclusión**: se entiende pero no es un terremoto (FR-009).
3. **Marca**: se guarda y se señala en `quality_flags` (FR-005, FR-006, FR-007, FR-010).
4. **Transformación**: cambia un valor y se señala (texto numérico → número; milisegundos → UTC).

El consumidor evalúa todas las reglas de cuarentena sin cortar en la primera, para listar todos
los motivos. Si hay algún motivo de cuarentena, no se evalúan marcas.

## R3. Qué reglas heredadas se retiran

| Regla heredada | Decisión | Razón |
|---|---|---|
| `magnitude_null` | Retirada: se conserva nula | Principio III: ausente no es cero ni error |
| `magnitude_out_of_range` (0–10) | Sustituida por la marca `magnitude_out_of_range` con rango plausible [−2, 10] | Magnitudes negativas legítimas; un valor raro se señala, no se rechaza |
| `event_too_old` (7 días, solo feed) | Retirada | Entran los huecos recuperados y la carga histórica por el mismo camino; la antigüedad no es un defecto |
| `future_timestamp` (rechazo) | Pasa a marca `future_time` | Un reloj desajustado no invalida el evento |
| `duplicate_id` | Retirada | Nunca se aplicó y la repetición la resuelve `apply_event_version` (FR-008) |
| `required_field_null`, `coordinates_*`, `id_invalid_type`, `time_invalid`, `updated_invalid` | Se mantienen, con códigos más finos por campo | Son los casos intratables de FR-002 |

## R4. Marcas de calidad (`quality_flags`)

| Marca | Condición | Dimensión |
|---|---|---|
| `negative_depth` | profundidad < 0 | Validez |
| `magnitude_out_of_range` | magnitud < −2 o > 10 | Validez |
| `depth_out_of_range` | profundidad > 800 km | Validez |
| `future_time` | ocurrencia > recepción + 5 min | Actualidad |
| `updated_before_time` | `updated` < `time` | Consistencia |
| `magnitude_from_text` / `depth_from_text` | llegó como texto numérico y se convirtió | Validez |
| `magnitude_not_numeric` / `depth_not_numeric` | llegó como texto no numérico; se guarda nulo | Validez |
| `extra_coordinates` | más de tres valores en `coordinates` | Validez |
| `ambiguous_country` | el punto cae en varias entidades | Consistencia |
| `synthetic` | mensaje de prueba dañado a propósito | — |

La magnitud negativa **no** se marca (FR-005): −0,02 es habitual en escalas locales. Un valor
nulo de origen tampoco lleva marca: se cuenta por la columna nula (FR-004). Una revisión
posterior sustituye el conjunto completo (ya lo hace `apply_event_version`).

## R5. Fechas

`time` y `updated` llegan en milisegundos Unix. Se convierten con `datetime.fromtimestamp(...,
tz=UTC)`; el valor original queda en `original_event`. `ingested_at` del mensaje (cuándo lo obtuvo
el productor) va a `message_log.produced_at`; `first_ingested_at` e `ingested_at` del modelo son
el tiempo de proceso del consumidor. Ya hay tres tiempos separados; esta funcionalidad no añade
columnas, solo lo documenta y lo mide.

## R6. Rechazo por el modelo

Se mantiene `model_constraint_violation` con el error de la base en el detalle (decisión de la
clarificación). Lo cubren los errores de integridad y de datos de asyncpg; los de conexión se
reintentan sin confirmar offsets, como ya hace el bucle (spec 002, R20).

## R7. Integración espacial

- **Decisión**: `SpatialEnricher.lookup` devuelve todas las entidades que contienen el punto
  (`intersects`, que incluye la frontera), ordenadas por `ADM0_A3`; elige la primera y devuelve
  una bandera de ambigüedad si hay más de una (FR-022).
- **Unicidad**: al construir el enriquecedor se comprueba que `ADM0_A3` no se repite ni falta y
  que todos existen en `core.dim_country`; si no, el consumidor no arranca con un mensaje que
  nombra los identificadores problemáticos (FR-020). La comprobación contra la base evita que el
  catálogo montado y la dimensión se desvíen.
- **Rendimiento**: 177 polígonos por punto bastan: 32.000 eventos se procesaron en unos 45 s con
  la implementación actual y esta no la empeora.
- **Aviso documentado**: escala 1:110.000.000, límites simplificados, sin precisión cartográfica
  (FR-023); el 77 % de «Sin país» observado se explica por eventos marinos y la simplificación de
  costas.
- **Alternativas**: índice espacial `STRtree` (innecesario a esta escala); asignar el país más
  cercano (prohibido por el principio IV).

## R8. Exclusiones en el consumidor

El productor solo publica terremotos, pero el consumidor debe tratar bien un mensaje de otro tipo
(FR-009). Se guarda en `excluded_event` con `ON CONFLICT DO NOTHING`; la extracción se toma del
mensaje solo si existe en `core.extraction` (subconsulta), para no violar la clave foránea. El
resultado en el registro de mensajes es `excluded`, valor que el modelo no admitía hoy (R9).

## R9. Cambios mínimos de modelo, justificados

FR-032 permite modificar el modelo «por necesidad demostrada». Hacen falta tres cambios, todos
aditivos y en una única plantilla idempotente `db/sql/041_consumer_quality.sql`:

| Cambio | Necesidad |
|---|---|
| `quarantine.reprocessed_at`, `reprocess_result`, `reprocess_reason_codes` (nulos) | FR-017: marcar cada fila reprocesada con fecha y resultado; sin esto no hay forma de saber qué se reprocesó (y no se puede ser idempotente) |
| `message_log.attempt smallint NOT NULL DEFAULT 0` y clave primaria `(kafka_topic, kafka_partition, kafka_offset, attempt)` | Aclaración 2: el reprocesado añade una fila con el mismo mensaje, que la clave actual impide |
| `message_log.outcome` admite también `excluded` | FR-009 y FR-015: la exclusión tiene que contarse |

La plantilla es idempotente (`IF NOT EXISTS`, bloques `DO`) para poder aplicarla al volumen
existente sin recrearlo. Se actualizan las sentencias `ON CONFLICT` del consumidor y de los
ayudantes de prueba, el contrato de base de datos de la 002 y el diccionario de datos.

## R10. Reprocesado

- **Decisión**: `docker compose run --rm quality-reprocess` (servicio bajo el perfil `tools`, imagen
  del consumidor) recorre las filas de cuarentena con `reprocessed_at IS NULL`, de las dos
  vistas (`core` y `replay`), y por cada una: reconstruye el mensaje desde `payload` o `raw_text`,
  aplica las reglas vigentes, y en una transacción (a) si pasa, llama a `apply_event_version` en
  el espacio del topic; (b) inserta la fila de `message_log` con `attempt = 1`; (c) marca la fila
  de cuarentena con la fecha, el resultado y los motivos vigentes.
- **Idempotencia**: solo toma filas sin `reprocessed_at`; el resultado `still_rejected` también
  fija la fecha, así que una segunda ejecución no hace nada. Una fila sintética se reprocesa
  igual y su evento conserva la marca `synthetic`.
- **Versión atrasada**: el evento puede tener ya una versión posterior; `apply_event_version`
  devuelve `stale` y no cambia el estado actual.
- **No se borra nada**: la fila de cuarentena y la fila `attempt = 0` de `message_log` permanecen.
- **Alternativas**: reproducir el mensaje por Kafka (obliga a un offset nuevo y duplica filas);
  borrar la cuarentena tras recuperar (pierde la constancia).

## R11. Casos sintéticos

- **Decisión**: un conjunto de casos en `tests/synthetic/cases.py`, cada uno con identificador
  `synthetic-<caso>`, el motivo o marca esperados y la descripción. `python -m
  tests.synthetic.inject` los publica al topic en vivo con `"synthetic": true` y
  `"synthetic_case": "<caso>"`; el consumidor, al ver `synthetic: true`, añade la marca
  `synthetic` y `is_synthetic = true`.
- **Idempotencia** (FR-026): antes de publicar, el inyector consulta la base y omite los casos
  cuyo `synthetic_case` ya consta (en cuarentena, historial o exclusiones por el prefijo del
  identificador).
- **Exclusiones sintéticas**: no tienen columna; se reconocen por el prefijo `synthetic-` del
  identificador, reservado y documentado (aclaración 3).
- **Consultas**: toda consulta de análisis real filtra `NOT ('synthetic' = ANY(quality_flags))` o
  `NOT is_synthetic`; el filtro está en un único sitio, las vistas de [data-model.md](data-model.md).
- **Alternativas**: un esquema aparte para sintéticos (rompería la prueba «con el sistema real»);
  una columna nueva (rechazada en la clarificación).

## R12. Recuentos por SQL

Un fichero `db/queries/quality.sql` con consultas con nombre (comentario `-- name:`), sin vistas
nuevas: cuarentena por motivo, eventos por marca, nulos por campo, recibidos por resultado,
versiones distintas, eventos actuales, retrasos. Una prueba las ejecuta contra datos conocidos y
la memoria cita cada una. **Sin contadores acumulados**: todo se calcula de lo almacenado.

## R13. Análisis de calidad en la memoria

Apartado «Calidad de los datos» de `docs/report.md` con una tabla por dimensión (comprobación,
consulta, denominador, resultado, acción, limitación) y antes/después donde hay tratamiento. El
«antes» sale de las cifras de partida de esta investigación y del reprocesado de la cuarentena; el
«después», de la misma consulta tras aplicar las reglas. Un script `tests/analysis/quality_report.py`
**no** se crea (no se exige automatizar): las consultas se ejecutan y se pegan.

## R14. Pruebas

- **Unitarias**: cada regla del catálogo (tabla de casos), asignación de país (puntos conocidos,
  frontera, océano, determinismo), unicidad del catálogo, coherencia catálogo-documento.
- **Con base real** (`tests/db`): consumidor con el modelo nuevo (cada caso a su destino),
  reprocesado (recuperación, persistencia del rechazo, idempotencia, espacio por topic, versión
  atrasada), conteo (recibidos = suma de resultados), filtro de sintéticos, reinicio a mitad.
- **Con el sistema real** ([quickstart.md](quickstart.md)): inyección de sintéticos, reprocesado de
  las 2 filas reales, evento marítimo, coordenadas inválidas, magnitud nula, reinicio del consumidor
  con 1.000 mensajes.
