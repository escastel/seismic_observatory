# Consultas del apartado de calidad (V8 · SC-009)

- Observado (UTC): 2026-11-16T13:15:13Z
- Rama y commit: 004-consumer-quality @ 76b3e91 (con cambios sin commit)
- Equipo: MINGW64_NT-10.0-26200 3.5.4-cbe555e0.x86_64 x86_64
- Motor: Docker 29.1.3 (Docker Desktop (containerized)), Compose 2.40.3-desktop.1; recursos del motor: 12 CPU, 7.6 GiB

| | V8 |
|---|---|
| Esperado | Cada consulta del apartado «Calidad de los datos» de `docs/report.md` se repite contra la base y da el resultado de la memoria (las cifras del feed crecen con el tiempo y llevan fecha) |
| Observado | Las 22 consultas de `db/queries/quality.sql` se ejecutan sin errores; los resultados de abajo son los citados en la memoria (corte 2026-11-16 13:40Z; el feed añade un evento cada pocos minutos, por eso la memoria cita 32.978 terremotos actuales y esta ejecución, anterior, 32.977) |
| Resultado | SUPERADA |

```bash
docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /queries/quality.sql'
```

## Salida completa

```text
outcome   | messages 
-------------+----------
 new         |    32976
 quarantined |        2
 revised     |      134
(3 rows)

   outcome   | messages 
-------------+----------
 excluded    |        2
 new         |     1013
 quarantined |       16
(3 rows)

 outcome | messages 
---------+----------
 new     |        1
 revised |        1
(2 rows)

   outcome   | messages 
-------------+----------
 quarantined |       16
(1 row)

 received | sum_of_outcomes | difference 
----------+-----------------+------------
    33112 |           33112 |          0
(1 row)

         reason         | messages 
------------------------+----------
 magnitude_out_of_range |        2
(1 row)

           reason           | messages 
----------------------------+----------
 coordinates_out_of_range   |        2
 coordinates_missing        |        1
 coordinates_not_finite     |        1
 coordinates_not_numeric    |        1
 geometry_missing           |        1
 geometry_not_point         |        1
 invalid_id                 |        1
 invalid_time               |        1
 invalid_updated            |        1
 malformed_json             |        1
 missing_id                 |        1
 missing_time               |        1
 missing_updated            |        1
 model_constraint_violation |        1
 not_an_object              |        1
(15 rows)

 rejected_messages | quarantine_rows | reason_entries 
-------------------+-----------------+----------------
                 2 |               2 |              2
(1 row)

 rejected_messages | quarantine_rows | reason_entries 
-------------------+-----------------+----------------
                16 |              16 |             16
(1 row)

 flag | events 
------+--------
(0 rows)

          flag          | events 
------------------------+--------
 synthetic              |   1013
 depth_from_text        |      1
 depth_not_numeric      |      1
 depth_out_of_range     |      1
 extra_coordinates      |      1
 future_time            |      1
 magnitude_from_text    |      1
 magnitude_not_numeric  |      1
 magnitude_out_of_range |      1
 negative_depth         |      1
 updated_before_time    |      1
(11 rows)

 current_earthquakes | magnitude_not_null | magnitude_pct | mag_type_not_null | mag_type_pct | depth_km_not_null | depth_km_pct | place_not_null | place_pct | country_id_not_null | country_id_pct 
---------------------+--------------------+---------------+-------------------+--------------+-------------------+--------------+----------------+-----------+---------------------+----------------
               32977 |              32977 |        100.00 |             32977 |       100.00 |             32977 |       100.00 |          32976 |    100.00 |                7624 |          23.12
(1 row)

 current_earthquakes | magnitude_not_null | magnitude_pct | mag_type_not_null | mag_type_pct | depth_km_not_null | depth_km_pct | place_not_null | place_pct | country_id_not_null | country_id_pct 
---------------------+--------------------+---------------+-------------------+--------------+-------------------+--------------+----------------+-----------+---------------------+----------------
                1013 |               1011 |         99.80 |              1013 |       100.00 |              1012 |        99.90 |           1013 |    100.00 |                 328 |          32.38
(1 row)

 distinct_versions | version_messages | difference 
-------------------+------------------+------------
             33112 |            33112 |          0
(1 row)

 duplicated_versions 
---------------------
                   0
(1 row)

 duplicated_event_ids 
----------------------
                    0
(1 row)

 invalid_coordinates 
---------------------
                   0
(1 row)

 updated_before_event 
----------------------
                    0
(1 row)

 missing_countries 
-------------------
                 0
(1 row)

 current_earthquakes |   median_minutes   |    p95_minutes     
---------------------+--------------------+--------------------
               32977 | 109178.12518333334 | 130843.31558333333
(1 row)

 current_earthquakes |  median_minutes   |    p95_minutes    
---------------------+-------------------+-------------------
               32977 | 523734.8785749667 | 934062.6920898033
(1 row)

 event_type | events | versions 
------------+--------+----------
(0 rows)
```

Cifras adicionales usadas en la memoria (consulta directa sobre `core.event_current`, sin
sintéticos): magnitud mínima −0,02 y máxima 8,8; profundidad mínima −2,74 km y máxima 683,6 km;
1 magnitud negativa; 5 profundidades negativas; 0 valores fuera del rango plausible; 445 eventos
del feed y 32.533 del catálogo; 135 versiones no actuales de 91 eventos.
