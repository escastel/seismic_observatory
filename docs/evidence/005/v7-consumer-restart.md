# V7 · Reinicio del consumidor a mitad de la reproducción

**Salida**: [v7-consumer-restart.out](v7-consumer-restart.out), [v7-start.out](v7-start.out) ·
**Consulta**: [sql/replay-state-fingerprint.sql](sql/replay-state-fingerprint.sql) (SC-006; prueba
«Reiniciar consumidor» del enunciado §11 aplicada a la reproducción).

Orden: `reset` y `start --start 2025-01-01 --end 2025-05-01 --min-mag 4.0 --rate 100` (unos 53 s), con
`docker compose restart consumer` lanzado cuando el estado marcaba 2.525 de 5.301 enviados.

| Comprobación | Esperado | Observado | Resultado |
|---|---|---|---|
| Reinicio en marcha | el consumidor vuelve y sigue | `Restarting` → `Started`; la reproducción continuó (2.726 enviados poco después) | ✔ |
| Final de la reproducción | 5.301 publicados, estado `finished` | «Reproducción terminada: 5301 eventos publicados» | ✔ |
| Huella de `replay.event_current` | igual que sin reinicio (V2) | **5.301 · 270575545300917288502**, idéntica | ✔ |
| Efectos duplicados | ninguno | `message_log`: `new` 5.301 y nada más; 5.301 versiones de 5.301 eventos; cuarentena 0 | ✔ |
| Errores en el consumidor | ninguno | 0 líneas con «traceback» o «ERROR» en el log de los últimos 15 min | ✔ |
| `core` | idéntico | `replay compare` salida 0 | ✔ |

La prueba con la base real y el reinicio simulado con relectura solapada de mensajes
(`tests/db/test_replay_consumer_restart.py`) cubre el caso que aquí no ocurrió: el consumidor
confirma el desplazamiento después de cada mensaje, así que el reinicio real no releyó ninguno. En esa
prueba, los 20 mensajes releídos dan `duplicate` y el estado final es idéntico, `replayed_at`
incluido.
