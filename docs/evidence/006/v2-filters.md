# V2 · Filtros start, end, min_mag y country_id

**Fecha**: 2026-11-16 18:54 UTC · **Rama**: `006-query-api` · **Resultado**: SUPERADA

Periodo cerrado de 2025 (no cambia con la ingesta en vivo). Se toma un evento real como referencia.

| Comprobación | Esperado | Observado | |
|---|---|---|---|
| start inclusivo | incluye us7000rlt6 en [t, t+1ms) | ['us7000rlt6'] | ✓ |
| end exclusivo | no incluye us7000rlt6 cuando end = su instante | False | ✓ |
| min_mag=6 | todos con mag >= 6 | 145 eventos | ✓ |
| country_id=JPN | todos con country_id JPN | 129 eventos | ✓ |
| combinados | subconjunto de ambos filtros | 0 eventos | ✓ |
| end sin start | ventana de 24 h anterior a end | {'start': 1748649600000, 'end': 1748736000000, 'default_applied': True} | ✓ |

## Notas

- Total de eventos reales de 2025: 18302.
