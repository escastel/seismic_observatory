# V8 · Truncado, total completo y paginación

**Fecha**: 2026-11-16 18:54 UTC · **Rama**: `006-query-api` · **Resultado**: SUPERADA

Periodo cerrado de 2025 con magnitud mínima 4; se recorren todas las páginas por `next_offset`.

| Comprobación | Esperado | Observado | |
|---|---|---|---|
| Máximo por defecto | limit=1000, count=1000 | limit=1000 count=1000 | ✓ |
| Truncado y total | truncated=true, total > 1000 | truncated=True total=18302 | ✓ |
| Cada evento una vez | 18302 ids únicos | 18302 ids, 18302 únicos, 19 páginas | ✓ |
| Orden estable (time desc, id asc) | orden global creciente en (-time, id) | comprobado en todas las páginas | ✓ |
| Última página | truncated=false, next_offset=null | truncated=False next=None | ✓ |
