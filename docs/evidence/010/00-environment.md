# Estado base (T001)

- Rama: `010-dashboard-refinements`; `.specify/feature.json` apunta a `specs/010-dashboard-refinements`.
- Equipo: Windows 11 (Git Bash), Node v24.22.1.
- `npm ci` y `npm test` en `frontend/` antes de cambiar nada: 13 ficheros, 142 pruebas, todas pasan.
- API local (Docker) sana. `GET /api/eventos?country_id=ALB`: `count` 0, `total` 0, `period.end` `null` en `/api/eventos` (válido en ese contrato).
- `git fetch`: `origin/main` en `0f4b4b4` (PR #10); la rama 010 parte de él más `ea74b60`, sin empujar.
