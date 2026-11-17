# Revisión de higiene del repositorio (T026)

**Fecha**: 2026-11-17 · **Rama**: `008-analysis-costs-deliverables` · Solo lectura sobre Git; no se imprimió `.env` ni se
ejecutó `docker compose config`. Las órdenes están al final.

| Comprobación | Esperado | Observado | Resultado |
|---|---|---|---|
| Ficheros versionados | — | 508 | — |
| `node_modules/`, `dist/`, `.env`, `*.bak`, `*.orig`, claves (`*.pem`, `*.key`), `*.csv`, `*.zip`, `*.gz`, `*.dump`, `.venv` | ninguno | ninguno | superada |
| Carpeta `data/` | solo `.gitkeep` | solo `data/.gitkeep` (el resto de coincidencias del patrón es `frontend/src/app/data/observatory.service.ts`, código del panel) | superada |
| `db/seeds/` | sin copias ni conjuntos | solo `.gitkeep` y `README.md` | superada |
| Ficheros versionados de más de 1 MB | ninguno | ninguno | superada |
| Secretos (patrones `authtoken`, `password`, `secret`, `api_key` con valor de 16 o más caracteres; formato de token de ngrok) | ninguno | ninguno | superada |
| `.env` ignorado | ignorado | `.gitignore:2` lo ignora; `frontend/node_modules` ignorado por `frontend/.gitignore` | superada |
| Enlaces simbólicos en el índice | solo `.claude/skills/*` de Netlify y ngrok (CLAUDE.md) | son los de esas skills | superada |
| Cambios de tipo (`T`) sin commitear | ninguno | ninguno | superada |
| Blobs de más de 1 MB **alcanzables desde las ramas remotas** (`origin/main`, `origin/002…007`) | ninguno | ninguno | superada |

## Hallazgo en el historial local (no corregido)

- El historial contiene, en commits antiguos, `db/seeds/historical_1900.jsonl`, `historical_2025.jsonl` y
  `historical_2026.jsonl`. El blob `db/seeds/historical_2026.jsonl` (98.595.604 bytes, commit `b472ec0`) **solo es
  alcanzable desde la rama local `backup/main-before-fix`**, que no está en el remoto (`git ls-remote --heads origin` no la
  lista).
- **Riesgo**: empujar esa rama (o `git push --all`) publicaría 98 MB de datos descargados, lo que el enunciado §12 y la
  constitución V prohíben.
- **Resuelto el 2026-11-17**: con confirmación explícita de la usuaria se borró la rama local `backup/main-before-fix`
  (`git branch -D`, estaba en `4c0a8c5`). El blob queda en el almacén de objetos hasta el siguiente `git gc`, pero ya no es
  alcanzable desde ninguna rama. No se reescribió el historial publicado.

## Órdenes

```bash
git ls-files | wc -l
git ls-files | grep -E '(^|/)node_modules/|(^|/)\.env$|\.bak$|\.orig$|(^|/)data/|\.(pem|key|p12)$|(^|/)dist/|\.(parquet|csv|zip|gz|dump)$|\.venv'
git ls-files -z | xargs -0 -I{} sh -c 'f="{}"; [ -f "$f" ] && s=$(wc -c < "$f") && [ "$s" -gt 1000000 ] && echo "$s $f"'
git grep -I -l -E '(authtoken|NGROK_AUTHTOKEN|password|secret|api[_-]?key)\s*[:=]\s*["'"'"']?[A-Za-z0-9_\-]{16,}'
git rev-list --objects origin/main origin/007-angular-dashboard | git cat-file --batch-check='%(objecttype) %(objectsize) %(rest)' | awk '$1=="blob" && $2>1000000'
git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | awk '$1=="blob" && $3>1000000'
git branch -a --contains b472ec0
```
