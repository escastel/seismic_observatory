# V9 · Reproducción identificada

**Fecha**: 2026-11-16 18:54 UTC · **Rama**: `006-query-api` · **Resultado**: SUPERADA

`mode=replay` sobre el espacio de reproducción cargado con la orden de la spec 005.

| Comprobación | Esperado | Observado | |
|---|---|---|---|
| Código | 200 | 200 | ✓ |
| Modo y etiqueta | mode=replay, label=REPRODUCCIÓN | replay / REPRODUCCIÓN | ✓ |
| replayed_at en cada feature | entero | [1794851910571, 1794851910561, 1794851910551, 1794851910541, 1794851910531] | ✓ |
| Sin ventana de 24 h | default_applied=false | {'start': None, 'end': None, 'default_applied': False} | ✓ |
| Datos históricos | eventos de 2025 | ['2025-04-30', '2025-04-30', '2025-04-30', '2025-04-30', '2025-04-30'] | ✓ |
| last_ingestion real | entero (consulta a USGS), no nulo | 1794855240682 | ✓ |
| last_replayed_at | entero | 1794851910571 | ✓ |
| exclude_synthetic | total sin sintéticos <= total | 5301 <= 5301 | ✓ |
| Estadísticas de reproducción | mode=replay y label REPRODUCCIÓN | replay / REPRODUCCIÓN | ✓ |
| Aviso de referencia en reproducción | avisa de que la referencia es solo lo reproducido | El periodo reciente puede estar incompleto: USGS añade y revisa eventos durante horas. La referencia se ha calculado solo sobre los datos reproducidos. | ✓ |
| mode desconocido | 422 | 422 {'error': 'invalid_parameters', 'detail': [{'param': 'mode', 'message': "must be 'live' or 'replay', got 'otro'"}]} | ✓ |
| Sin mode = live | sin etiqueta | None | ✓ |
