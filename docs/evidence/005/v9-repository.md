# V9 · Material heredado y repositorio

**Salida**: [v9-repository.out](v9-repository.out) (requisito FR-019; norma «Repositorio público y
datos» de `CLAUDE.md`).

| Comprobación | Esperado | Observado | Resultado |
|---|---|---|---|
| `git ls-files db/seeds` | solo `.gitkeep` y `README.md` | exactamente esos dos | ✔ |
| `git ls-files data` | solo `.gitkeep` | `data/.gitkeep` | ✔ |
| Datos ignorados | `data/replay/*`, `data/usgs/catalog/*` y `db/seeds/*.jsonl` ignorados | `git check-ignore` lo confirma para los tres | ✔ |
| Ficheros de más de 500 kB sin versionar o modificados | ninguno | ninguno | ✔ |
| Copias `*.bak` / `*.orig` en `db/seeds/` | ninguna | ninguna | ✔ |
| `.env` versionado | no | no | ✔ |

## Destino del material heredado (decisión R9 de la spec)

| Elemento | Decisión | Motivo |
|---|---|---|
| `producer/app/replay.py` | sustituido por el paquete `producer/app/replay/` | publicaba un JSONL a ritmo fijo; ahora la selección sale del catálogo descargado, se registra y se controla |
| `db/seeds/historical_2025.jsonl` (seis eventos ficticios) | retirado | los casos útiles (versiones del mismo identificador, rechazos) los cubre el conjunto sintético, con resultado esperado comprobable |
| `db/seeds/historical_1900.jsonl` (35 eventos reales) | retirado de Git | es un conjunto descargado; se regenera con `docker compose run --rm catalog-loader`; ninguna prueba lo usa |
| `tests/unit/test_replay.py`, `tests/unit/test_history.py` | retirados | probaban el lector del módulo sustituido |
| `tests/integration/load_test.py` | adaptado a la orden nueva | su medición SC-006 llamaba a la orden antigua |
