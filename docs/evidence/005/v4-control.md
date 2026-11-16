# V4 · Pausar, reanudar y detener

**Salida**: [v4-control.out](v4-control.out), [v4-start.out](v4-start.out) · **Consulta**:
[sql/v4-order-and-gaps.sql](sql/v4-order-and-gaps.sql) (requisitos FR-008 a FR-010; criterio SC-008).

Se reprodujo enero de 2025 (1.413 eventos) a 20 eventos/s en una terminal y se controló desde otra con
`docker compose run --rm replay <orden>`. La reproducción lenta es deliberada: da tiempo a actuar.

| Paso | Esperado | Observado | Resultado |
|---|---|---|---|
| Segundo `start` con uno activo | rechazado, código 4, sin publicar ni registrar | «Ya hay una reproducción activa: espere a que termine o ejecute `replay stop`», salida 4 | ✔ |
| `reset` con una reproducción activa | rechazado, código 4 | «Hay una reproducción activa: no se puede ejecutar reset», salida 4 | ✔ |
| `pause` | estado `paused` en menos de 2 s; no se publica más | `paused` **0,41 s** después de volver la orden (incluye el sondeo de 0,25 s del ejecutor y el mío de 0,1 s); `sent` = 207 constante durante los 6 s siguientes | ✔ |
| `status` en pausa | estado, enviados, restantes, objetivo | «en pausa; enviados 207; restantes 1206; objetivo 20.0 eventos/s» | ✔ |
| `resume` | continúa por el siguiente evento | `running`; 4 s después, `sent` = 292 | ✔ |
| `stop` | termina; lo publicado se conserva | `stopped`, 336 de 1.413 publicados; 3 s después `sent` sigue en 336; el ejecutor imprimió «Reproducción detenida: 336 de 1413 eventos publicados» y salió con 0 | ✔ |
| Sin saltos ni repeticiones | offsets contiguos, sin repetidos, en orden de tiempo | 336 mensajes, `no_repeated_offsets` = t, `no_gaps` = t, `out_of_time_order` = 0; `replay.event_current` = 336 = mensajes `new` | ✔ |

## Límites de la medición

- Los 0,41 s se miden desde que vuelve la orden `pause` (la propia orden tarda unos segundos en
  arrancar su contenedor, y mientras tanto la reproducción avanza: de 63 a 207 enviados entre el
  estado previo y la pausa). Es el tiempo de reacción del ejecutor, no el de toda la orden.
- Prueba equivalente con reloj simulado en `tests/unit/test_replay_runner.py` (pausa visible en menos
  de 0,25 s) y con la base real en `tests/db/test_replay_control_flow.py`.
