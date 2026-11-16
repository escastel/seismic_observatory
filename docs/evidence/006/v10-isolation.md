# V10 · Aislamiento: modo real idéntico antes y después de reproducir

**Fecha**: 2026-11-16 18:54 UTC · **Rama**: `006-query-api` · **Resultado**: SUPERADA

Se toma una instantánea de la API en modo real sobre el periodo cerrado de 2025, se reinicia y reproduce una selección (`replay reset` y `replay start`, spec 005) y se repite. Un identificador presente en ambos espacios se devuelve con sus valores en cada modo.

| Comprobación | Esperado | Observado | |
|---|---|---|---|
| Tras reset, reproducción vacía | total 0, etiqueta presente, 200 | 200 total=0 label=REPRODUCCIÓN | ✓ |
| Modo real igual tras reset | idéntico | idéntico | ✓ |
| Reproducción persistida | > 0 eventos en modo replay | 2807 | ✓ |
| Modo real: eventos 2025 total | 18302 | 18302 | ✓ |
| Modo real: eventos 2025 min_mag=4 | 18302 | 18302 | ✓ |
| Modo real: eventos 2025 sin país | 129 | 129 | ✓ |
| Modo real: estadísticas 2025 total | 18302 | 18302 | ✓ |
| Modo real: estadísticas 2025 por país | [{"count": 14350, "country_id": null, "country_name": "Sin p | [{"count": 14350, "country_id": null, "country_name": "Sin p | ✓ |
| Modo real: estadísticas 2025 magnitud | {"items": [{"count": 16173, "from": 4, "to": 5}, {"count": 1 | {"items": [{"count": 16173, "from": 4, "to": 5}, {"count": 1 | ✓ |
| Modo real: estadísticas 2025 horas (suma) | 18302 | 18302 | ✓ |
| Todo lo reproducido con replayed_at y etiqueta | etiqueta + replayed_at | REPRODUCCIÓN / 1000 features | ✓ |
| Mismo id us6000pxh0 en ambos espacios | real sin replayed_at y reproducción con replayed_at | real=presente sin replayed_at=True; replay presente con replayed_at=True | ✓ |

## Notas

- Antes: espacio de reproducción con 2807 eventos.
- replay reset → código 0
- replay start (2025-01-01 a 2025-03-01, magnitud ≥ 4, 300 ev/s) → código 0; salida final: SelecciÃ³n registrada: 2807 eventos, primero 2025-01-01T00:13:22Z, Ãºltimo 2025-02-28T23:27:01Z, extraction_id 621 ReproducciÃ³n terminada: 2807 eventos publicados
