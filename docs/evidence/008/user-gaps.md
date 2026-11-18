# Huecos que ejecuta la persona autora (T027)

Comprobaciones que necesitan otro equipo, otro dispositivo u otra persona. Ya no queda ninguna pendiente. G3 y G4 se ejecutaron el 2026-11-17 (G3 con alcance reducido). G1 (puertos cerrados desde otro dispositivo) y G2 (arranque por una persona ajena) se retiraron del
seguimiento a petición de la persona autora; T057 de la spec 002 se dio por superada según lo informado (2,5 min, sin dudas) y la prueba V2 de la 002 desde otro dispositivo, igual que 003 T050 y los escenarios
reales de 005 y 006 en Linux, se descartaron por no ser requisito del enunciado (constan así en sus README).

| Id | Hueco | Origen | Dónde |
|---|---|---|---|
| G3 | Pruebas en Linux de las specs 002, 003, 005 y 006 | 002, 003, 005, 006 | **HECHO el 2026-11-17 con alcance reducido** ([linux-g3.md](linux-g3.md)): arranque con los cinco servicios `healthy` y suite completa de 886 pruebas en verde; la latencia salió con 0 eventos (no concluyente); 003 T050 y los escenarios reales de 005 y 006 se descartaron |
| G4 | Panel desde otro dispositivo físico (túnel y Netlify) | 007; §11 pruebas 9 y 10 | **HECHO el 2026-11-17** (móvil con datos móviles; [007 M1 a M3](../007/README.md)) |

## G3 · Linux (specs 002, 003, 005, 006) — HECHO el 2026-11-17 con alcance reducido

Ver [linux-g3.md](linux-g3.md): `docker compose up --build -d --wait` (cinco servicios `healthy`) y `pytest tests` (886 pruebas en verde). No se hizo la comprobación 003 T050 ni se repitieron los escenarios con el sistema real de las specs 005 y 006: se descartaron por no ser requisito del enunciado.

## G4 · Panel desde otro dispositivo físico (007; §11 pruebas 9 y 10) — HECHO el 2026-11-17 ([007 M1 a M3](../007/README.md))

1. Levantar el stack y el túnel (`docker compose --profile tunnel up -d` o el agente de ngrok en el host).
2. Abrir la URL de Netlify en el móvil con datos móviles (otra red).
3. **Esperado**: el panel carga mapa, gráficos y tabla con datos de las últimas 24 h y el estado «Datos al día».
4. Parar el túnel; **esperado**: en el siguiente refresco (≤ 60 s) aviso de backend inaccesible conservando la última lectura
   identificada como tal. Reabrir el túnel; **esperado**: recuperación sin recargar en ≤ 60 s.
5. Guardar capturas en `docs/evidence/007/` y completar la sección «Sigue sin probarse» de su README.
