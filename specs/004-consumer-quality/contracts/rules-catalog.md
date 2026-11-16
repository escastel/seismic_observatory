# Catálogo de reglas del consumidor

Cada regla tiene un código estable. `consumer/app/rules.py` es la fuente; una prueba comprueba que
este documento y el módulo contienen exactamente los mismos códigos.

## Cuarentena (el mensaje no puede tratarse)

| Código | Dimensión | Condición | Justificación |
|---|---|---|---|
| `malformed_json` | Validez | El mensaje no es JSON (o contiene `NaN`/`Infinity`) | No hay nada que interpretar; se guarda el texto recibido |
| `not_an_object` | Consistencia | El JSON no es un objeto | Sin campos que leer |
| `missing_id` | Completitud | Falta `id` | Sin identidad no hay evento |
| `invalid_id` | Consistencia | `id` no es texto no vacío | Idem |
| `missing_time` | Completitud | Falta `time` | Sin tiempo de ocurrencia no se puede situar |
| `invalid_time` | Validez | `time` no es un instante en milisegundos Unix | Idem |
| `missing_updated` | Completitud | Falta `updated` | Sin él no hay identidad de versión |
| `invalid_updated` | Validez | `updated` no es un instante en milisegundos Unix | Idem |
| `geometry_missing` | Completitud | Falta `geometry` | Sin posición no hay punto |
| `geometry_not_point` | Validez | `geometry.type` no es `Point` | Solo se admiten puntos |
| `coordinates_missing` | Completitud | `coordinates` no tiene longitud y latitud | Posición incompleta |
| `coordinates_not_numeric` | Validez | Longitud o latitud no numéricas | No se puede situar |
| `coordinates_not_finite` | Validez | Longitud o latitud NaN o infinitas | Idem |
| `coordinates_out_of_range` | Validez | Longitud fuera de [−180, 180] o latitud fuera de [−90, 90] | Coordenada imposible: ningún punto inventado |
| `model_constraint_violation` | Consistencia | El modelo de datos rechaza la versión (p. ej. fecha anterior a 1900) | El modelo es la última barrera; no se replican sus restricciones |

## Exclusión (se entiende, pero no es un terremoto)

| Código | Dimensión | Condición |
|---|---|---|
| `not_earthquake` | Consistencia | `properties.type` distinto de `earthquake` |
| `missing_type` | Completitud | Falta `properties.type` |

## Marcas (se guarda y se señala)

| Marca | Dimensión | Condición |
|---|---|---|
| `negative_depth` | Validez | Profundidad < 0 |
| `magnitude_out_of_range` | Validez | Magnitud < −2 o > 10 |
| `depth_out_of_range` | Validez | Profundidad > 800 km |
| `future_time` | Actualidad | `time` posterior a la recepción en más de 5 minutos |
| `updated_before_time` | Consistencia | `updated` anterior a `time` |
| `magnitude_from_text`, `depth_from_text` | Validez | Llegó como texto numérico y se convirtió |
| `magnitude_not_numeric`, `depth_not_numeric` | Validez | Llegó como texto no numérico; se guarda nulo |
| `extra_coordinates` | Validez | Más de tres valores en `coordinates` |
| `ambiguous_country` | Consistencia | El punto cae en varias entidades; se elige la de `ADM0_A3` menor |
| `synthetic` | — | Mensaje de prueba dañado a propósito |

## Lo que NO es una regla

- Magnitud, tipo de magnitud, profundidad o lugar nulos: se conservan nulos y se cuentan por la
  columna nula; no llevan marca.
- Magnitud negativa: valor legítimo de las escalas locales.
- Antigüedad del evento, repetición del identificador y topic de origen: no rechazan nada.

## Retiradas respecto a la spec 002

`magnitude_null`, `magnitude_out_of_range` como rechazo (0–10), `event_too_old`,
`future_timestamp` como rechazo y `duplicate_id`. Las filas de cuarentena que dejaron son las que
reprocesa [reprocess.md](reprocess.md).
