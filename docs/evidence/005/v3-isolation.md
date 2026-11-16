# V3 · Aislamiento de `core`

**Salida completa**: [v2-v3-replay-5000.out](v2-v3-replay-5000.out),
[v5-repeat.out](v5-repeat.out), [v6-synthetic.out](v6-synthetic.out),
[v7-consumer-restart.out](v7-consumer-restart.out) · Procedimiento:
[isolation-check.md](../../../specs/005-historical-replay/contracts/isolation-check.md)
(requisito FR-013; criterio SC-003).

**Procedimiento**: productor en vivo parado; consumidor al día; `replay snapshot` (recuento y suma de
comprobación de cada tabla de `core`); reproducción; consumidor al día; `replay compare`.

## Instantánea (antes de reproducir)

| Tabla de `core` | Filas | | Tabla de `core` | Filas |
|---|---:|---|---|---:|
| `dim_country` | 177 | | `message_log` | 34.232 |
| `dim_date` | 49.673 | | `publish_state` | 33.024 |
| `event_current` | 34.037 | | `quarantine` | 18 |
| `event_version` | 34.196 | | `raw_payload` | 158 |
| `excluded_event` | 2 | | `extraction` | 495 (sin contar `replay_selection`) |

Cada tabla lleva además su suma de comprobación (`hashtextextended` de cada fila, independiente del
orden), en el JSON de la salida.

## Resultado

| Después de… | `replay compare` | Código |
|---|---|---:|
| V2: 5.301 eventos reproducidos | «core idéntico a la instantánea: el aislamiento se mantiene» | 0 |
| V4: reproducción parcial, pausa, parada y `reset` | idéntico | 0 |
| V5: `reset` y repetición completa | idéntico | 0 |
| V6: casos sintéticos | idéntico | 0 |
| V7: reproducción con reinicio del consumidor | idéntico | 0 |

**Esperado**: 0 tablas con diferencias en cada comparación. **Observado**: 0 en las cinco. ✔

La única diferencia admitida, y por eso excluida de la comparación, es la fila que cada selección
deja en `core.extraction` con `purpose = 'replay_selection'`: es la constancia que exige la spec. En
la base hay ahora 8 filas de ese tipo (554, 556 a 562; el 555 lo usó el productor en vivo); la instantánea las cuenta aparte.

## Detección de una alteración

El mecanismo no es una comparación que siempre da «igual»: las pruebas
`tests/db/test_replay_isolation_check.py` comprueban que una fila alterada, insertada o borrada en
`core.event_current` aparece como diferencia, y que una tabla nueva se incluye sola.

## Límites

- Válido solo con el productor en vivo parado (si no, el feed real cambia `core`); se reanudó al
  terminar.
- La suma de comprobación detecta cualquier cambio de contenido con probabilidad de colisión
  despreciable para este tamaño, pero no es una prueba criptográfica.
