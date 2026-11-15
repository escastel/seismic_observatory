# Estructura creada y privilegios (V3, V7)

- Observado (UTC): 2026-11-15T00:50:49Z
- Rama y commit: 002-platform-data-model @ a0eb6e1 (con cambios sin commit)
- Equipo: MINGW64_NT-10.0-26200 3.5.4-cbe555e0.x86_64 x86_64
- Motor: Docker 29.1.3 (Docker Desktop (containerized)), Compose 2.40.3-desktop.1; recursos del motor: 12 CPU, 7.6 GiB

| | V3 | V7 |
|---|---|---|
| Esperado | Tablas de data-model.md en `core`, las seis de eventos en `replay`, 177 países, 1900-01-01 a 2035-12-31 con 49.673 días | `permission denied` para `observatory_reader` |
| Observado | 10 tablas en `core`, 6 en `replay`, 177 países, 1900-01-01 a 2035-12-31 con 49.673 días | `ERROR: permission denied for table event_current` |
| Resultado | SUPERADA | SUPERADA |

Base creada por `db/init/00-init.sh` en el último arranque desde cero de [cold-starts.md](cold-starts.md), sin pasos manuales.

## Salida

```text
$ \dt core.* / \dt replay.*
               List of relations
 Schema |      Name      | Type  |    Owner     
--------+----------------+-------+--------------
 core   | dim_country    | table | observatorio
 core   | dim_date       | table | observatorio
 core   | event_current  | table | observatorio
 core   | event_version  | table | observatorio
 core   | excluded_event | table | observatorio
 core   | extraction     | table | observatorio
 core   | message_log    | table | observatorio
 core   | publish_state  | table | observatorio
 core   | quarantine     | table | observatorio
 core   | raw_payload    | table | observatorio
(10 rows)

               List of relations
 Schema |      Name      | Type  |    Owner     
--------+----------------+-------+--------------
 replay | event_current  | table | observatorio
 replay | event_version  | table | observatorio
 replay | excluded_event | table | observatorio
 replay | message_log    | table | observatorio
 replay | publish_state  | table | observatorio
 replay | quarantine     | table | observatorio
(6 rows)

$ dimensiones
177
1900-01-01|2035-12-31|49673
$ V7: psql -U observatory_reader -c "delete from core.event_current"
ERROR:  permission denied for table event_current
exit=1
```
