# Reprocesado de la cuarentena (US2: V4)

- Observado (UTC): 2026-11-16T13:14Z a 2026-11-16T13:18Z
- Rama y commit: 004-consumer-quality @ 1d469f4
- Equipo: MINGW64_NT-10.0-26200 3.5.4-cbe555e0.x86_64 x86_64
- Motor: Docker 29.1.3 (Docker Desktop (containerized)), Compose 2.40.3-desktop.1; recursos del motor: 12 CPU, 7,6 GiB

| | V4 |
|---|---|
| Esperado | Las filas rechazadas por reglas retiradas pasan al estado actual; las que siguen siendo intratables quedan `still_rejected` con sus motivos vigentes; nada se borra; la segunda ejecución no cambia nada; el registro distingue el resultado original del reprocesado |
| Observado | Las 2 filas reales (magnitud −0,02, rechazada por la regla 0–10 retirada) se recuperaron (`recovered_new` y `recovered_revised`); las 16 sintéticas siguieron rechazadas con su motivo; 18 filas de cuarentena conservadas; la segunda ejecución: «pendientes=0»; 18 filas `attempt = 1` junto a las originales |
| Resultado | SUPERADA |

## Antes

```text
 quarantine_id | kafka_offset |  event_id  | reason_codes             | is_synthetic | reprocessed_at
---------------+--------------+------------+--------------------------+--------------+---------------
             1 |          220 | ci41362415 | {magnitude_out_of_range} | f            |
             2 |          336 | ci41362415 | {magnitude_out_of_range} | f            |

eventos_reales 32.976 · cuarentena_real 2 · pendientes 18 · filas_reprocesado 0
```

## Simulacro (`--dry-run`, no escribe)

```text
$ docker compose run --rm quality-reprocess --dry-run
SIMULACION [core] fila 1 evento=ci41362415 -> recovered_new
SIMULACION [core] fila 2 evento=ci41362415 -> recovered_new
SIMULACION [core] fila 3 … fila 18 -> still_rejected  (motivos vigentes de cada una)
Resumen: pendientes=18 recuperadas=2 siguen rechazadas=16 (simulacion: no se escribio nada)
```

## Ejecución y repetición

```text
$ docker compose run --rm quality-reprocess
[core] fila 1 evento=ci41362415 -> recovered_new
[core] fila 2 evento=ci41362415 -> recovered_revised
Resumen: pendientes=18 recuperadas=2 siguen rechazadas=16
$ docker compose run --rm quality-reprocess
Resumen: pendientes=0 recuperadas=0 siguen rechazadas=0
```

## Después

```text
 reprocess_result  | count
-------------------+-------
 recovered_new     |     1
 recovered_revised |     1
 still_rejected    |    16

 event_id   | magnitude | quality_flags | country_id | updated_at
------------+-----------+---------------+------------+---------------------------
 ci41362415 |     -0.02 | {}            | USA        | 2026-11-15 14:31:06.44+00

 kafka_offset | attempt | outcome
--------------+---------+-------------
          220 |       0 | quarantined       (tratamiento original, conservado)
          220 |       1 | new               (reprocesado)
          336 |       0 | quarantined
          336 |       1 | revised

eventos_reales 32.977 (+1) · filas de cuarentena 18 (ninguna borrada) · pendientes 0
filas_reprocesado (attempt = 1) 18 · filas originales (attempt = 0) 33.143
```

La magnitud −0,02 se conserva sin marca (FR-005: es un valor legítimo de las escalas locales).
Era justo el tipo de evento que la regla heredada de 0–10 hacía desaparecer del análisis. Las 16
filas sintéticas siguen rechazadas porque son casos dañados a propósito: el reprocesado las trata
igual que las reales y su resultado queda registrado.
