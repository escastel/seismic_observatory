# V11 · Estadísticas: ventanas, países, distribuciones y comparación

**Fecha**: 2026-11-16 18:54 UTC · **Rama**: `006-query-api` · **Resultado**: SUPERADA

Periodo cerrado de 2025. Se compara cada agregación con el total del mapa y con la suma de sus partes.

| Comprobación | Esperado | Observado | |
|---|---|---|---|
| total = mapa (sin filtros extra) | 18302 | 18302 | ✓ |
| total = mapa (min_mag=4) | 18302 | 18302 | ✓ |
| total = mapa (min_mag=6) | 145 | 145 | ✓ |
| total = mapa (country_id=JPN) | 129 | 129 | ✓ |
| total = mapa (country_id=JPN y min_mag=5) | 5 | 5 | ✓ |
| total = mapa (mes de marzo) | 1178 | 1178 | ✓ |
| Ventanas de una hora | 8760 ventanas (8760), suma = total | 8760 ventanas, suma 18302 | ✓ |
| Ventanas alineadas a la hora UTC | start % 3600000 == 0 | todas | ✓ |
| Horas vacías con 0 | alguna ventana con count 0 | 1550 | ✓ |
| Países suman el total | 18302 | 18302 | ✓ |
| «Sin país asignado» | categoría válida con su recuento | [{'country_id': None, 'country_name': 'Sin país asignado', 'count': 14350}] | ✓ |
| Distribución de magnitud | tramos + sin valor = total | 18302 + 0 | ✓ |
| Distribución de profundidad | tramos + sin valor = total | 18302 + 0 | ✓ |
| Comparación | recent, baseline (días 365), ratio, aviso | {'recent': {'start': 1794768844709, 'end': 1794855244709, 'count': 15}, 'baseline': {'year': 2025, 'events': 18302, 'days': 365, 'daily_mean': 50.14246575342466}, 'ratio': 0.29914763413834555} | ✓ |
| Denominador con días vacíos | daily_mean = eventos / 365 | 18302/365 = 50.14246575342466 | ✓ |
| ND con media cero | ratio = ND | ND | ✓ |
| Periodo, filtros, unidad | presentes | {'period': {'start': 1735689600000, 'end': 1767225600000, 'default_applied': False}, 'filters': {'min_mag': 4.0, 'country_id': None, 'exclude_synthetic': False}, 'unit': 'events'} | ✓ |
| Más de 10.000 ventanas | 422 pidiendo acotar | 422 {'error': 'invalid_parameters', 'detail': [{'param': 'start', 'message': 'the period has 52608 hourly windows; narrow it to at most 10000 hours'}]} | ✓ |
