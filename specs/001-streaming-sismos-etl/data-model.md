# Data Model: Streaming de sismos con ETL y consulta geoespacial

## Modelo dimensional

```text
dim_geografia 1 ───< fact_sismos >─── 1 dim_tiempo
                         |
                         └── external_id UNIQUE

cuarentena (independiente; conserva payload y motivo de calidad)
```

## Entidades y campos

### `dim_geografia`

Representa la clasificación espacial estable de un punto.

| Campo | Tipo lógico | Reglas |
|---|---|---|
| `geografia_key` | entero | clave sustituta, primaria |
| `country` | texto | país Natural Earth o `Sin país asignado`; no nulo |
| `continent` | texto | continente o valor explícito no asignado |
| `subregion` | texto | subregión o valor explícito no asignado |
| `source_dataset` | texto | versión/origen de Natural Earth |
| `geometry_hash` | texto | identifica la referencia espacial usada |

Debe existir una clave única sobre la combinación de clasificación y dataset. Debe
existir un índice B-Tree sobre `country` para filtros de API.

### `dim_tiempo`

Representa el calendario de la observación.

| Campo | Tipo lógico | Reglas |
|---|---|---|
| `tiempo_key` | entero | clave sustituta, primaria |
| `event_date` | fecha | no nula |
| `year` | entero | derivado |
| `month` | entero | 1-12 |
| `day` | entero | 1-31 |
| `week` | entero | semana ISO |

Debe existir una clave única sobre `event_date`.

### `fact_sismos`

Representa una observación sísmica aceptada y su última versión conocida.

| Campo | Tipo lógico | Reglas |
|---|---|---|
| `sismo_key` | entero | clave sustituta, primaria |
| `external_id` | texto | identificador USGS, único y no nulo |
| `updated` | timestamp | versión temporal del evento, no nulo |
| `event_time` | timestamp | fecha del sismo, no nulo |
| `magnitude` | decimal | numérica, dentro del rango aceptado |
| `longitude` | decimal | finita, -180 a 180 |
| `latitude` | decimal | finita, -90 a 90 |
| `depth_km` | decimal | finita cuando exista |
| `place` | texto | descripción original |
| `geografia_key` | entero | FK a `dim_geografia` |
| `tiempo_key` | entero | FK a `dim_tiempo` |
| `source_topic` | texto | `terremotos_raw` o `terremotos_replay` |
| `ingested_at` | timestamp | momento de persistencia |

Índices B-Tree obligatorios: `event_time` para rangos temporales,
`geografia_key` para joins/filtro de país y `external_id` único para idempotencia.
El upsert solo actualiza cuando `excluded.updated > fact_sismos.updated`.

### `cuarentena`

Conserva todo evento que no puede pasar el WAF.

| Campo | Tipo lógico | Reglas |
|---|---|---|
| `quarantine_key` | entero | clave primaria |
| `external_id` | texto nullable | si pudo extraerse |
| `received_at` | timestamp | no nulo |
| `source_topic` | texto | origen |
| `quality_dimension` | enum/texto | Una de las 7 dimensiones: Completitud, Validez, Exactitud, Consistencia, Oportunidad, Unicidad o Frescura |
| `reason_code` | texto | código estable |
| `reason_detail` | texto | explicación concreta |
| `payload` | JSON | evento original |
| `kafka_partition` | entero | trazabilidad |
| `kafka_offset` | entero | trazabilidad |

## Reglas y transiciones

1. `received` → `quarantined` si falla cualquier regla WAF; la inserción de
   cuarentena se confirma antes del offset.
2. `received` → `enriched` si magnitud y coordenadas son válidas.
3. `enriched` → `inserted` si no existe `external_id`.
4. `enriched` → `updated` solo si `updated` es posterior.
5. `enriched` → `unchanged` si `updated` es igual o anterior; no se crea duplicado.
6. `inserted|updated|unchanged|quarantined` → offset confirmado solo tras commit DB.

## Mapeo de calidad

- Nulo de magnitud, `id` o `updated`: **Fallo de Completitud**.
- Coordenadas fuera de rango o no numéricas: **Fallo de Validez**.
- Valor imposible o geometría no interpretable: **Fallo de Exactitud**.
- Tipos/fechas incompatibles entre campos: **Fallo de Consistencia**.
- Evento con `updated` inválido: **Fallo de Oportunidad**.
- `time` futuro más de 300 segundos o evento raw con más de 7 días: **Fallo de
  Frescura**.
- Identificador repetido con versión no posterior: **Fallo de Unicidad** cuando se
  registre como rechazo; el upsert debe conservar el dato vigente.

## Integridad

- Las FK de `fact_sismos` son obligatorias.
- `country = 'Sin país asignado'` no autoriza rellenar un país vecino.
- Los datos originales se conservan en el evento Kafka y en cuarentena cuando hay
  rechazo.
- La inicialización SQL debe ser repetible sin destruir el volumen existente.
