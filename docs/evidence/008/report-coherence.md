# Coherencia de `docs/report.md` (T025)

**Fecha**: 2026-11-17 · Comprobación con un script de lectura (enlaces relativos y anclas) y revisión de las cifras repetidas.

| Comprobación | Esperado | Observado | Resultado |
|---|---|---|---|
| Enlaces relativos de `report.md`, `evaluacion-financiera.md`, `guion-explicacion.md` y las matrices de `docs/evidence/008/` (fuera de bloques de código) | todos resuelven | 267 enlaces, 0 rotos | superada |
| Índice del principio de `report.md` | cada entrada enlaza con un encabezado existente | 13 entradas, 0 anclas sin encabezado | superada |
| Intro de `report.md` | describe el contenido actual | estaba desactualizada («solo la spec 002»); reescrita, con índice y nota sobre instantes de las cifras | corregida |
| «unos 16.000 eventos» del histórico | cifra coherente con la carga real | el enunciado estima 16.000 y la carga real tiene 18.302; ahora se dice así en «Alcance» y en «Índices» | corregida |
| Recuento de reproducción 5.301 (verificación de la 005) frente a 2.807 (estado actual) | distinguidos por instante | se aclara en la sección de análisis que el recuento cambia con cada reproducción | corregida |
| Eventos de `core`: 33.112 mensajes / 32.978 terremotos (calidad, 2026-11-16), 34.045 (API 006, 2026-11-16), 34.207 (2026-11-17) | no contradictorios | son instantes distintos del feed en vivo; la intro lo explica | corregida |
| Cifras repetidas del análisis (18.302; 14.350; 50,14; 1.013) en análisis, costes y evidencias | iguales | iguales en `report.md`, `analysis-queries.md` y `cost-measurements.md` | superada |

**No se ha modificado** el texto de calidad, reproducción, API ni panel más allá de lo anterior: sus cifras son del instante que cada una indica.
