# País y recuentos de calidad (US3 y US4: V5, V6)

- Observado (UTC): 2026-11-16T13:25Z a 2026-11-16T13:40Z
- Rama y commit: 004-consumer-quality @ dde1c24
- Equipo: MINGW64_NT-10.0-26200 3.5.4-cbe555e0.x86_64 x86_64
- Motor: Docker 29.1.3 (Docker Desktop (containerized)), Compose 2.40.3-desktop.1; recursos del motor: 12 CPU, 7,6 GiB

| Escenario | Esperado | Observado | Resultado |
|---|---|---|---|
| V5 · País | Interior, océano, frontera y determinismo; catálogo con identificador repetido falla al arrancar; el país no sale del texto | `tests/unit/test_spatial.py` (8) y `tests/db/test_consumer_country.py` (4) en verde; evento de `place` «Madrid» en el Pacífico queda sin país | SUPERADA |
| V5 · Antes/después de la regla | La regla determinista no empeora lo guardado | Recalculados con el código nuevo los 32.977 eventos reales: **0 cambian de país** y 0 puntos con varias entidades | SUPERADA |
| V6 · Recuentos | recibidos = nuevos + revisados + atrasados + repetidos + excluidos + rechazados, diferencia 0; recuentos por motivo y por marca con denominador; lo sintético aparte | `received 33112 · sum_of_outcomes 33112 · difference 0`; 22 consultas sin errores; reales y sintéticos por separado | SUPERADA |

## País: antes y después

```text
$ python -m tests.analysis._recheck_country        (script temporal, no versionado)
eventos reales analizados: 32977
cambian de país con la regla nueva: 0 []
puntos con varias entidades (ambiguos): 0 []
  con país -> con país 7624
  sin país -> sin país 25353
```

El 77 % (25.353) de los terremotos reales no cae en ningún polígono. Es lo esperado con datos de
2025 y 2026 de magnitud ≥ 4: la mayoría son marinos, y el catálogo está simplificado
(1:110.000.000), lo que recorta costas e islas pequeñas. No se atribuyen al país más cercano
(principio IV): quedan con país nulo, «Sin país asignado», y siguen contando en todos los totales.

## Recuentos (`db/queries/quality.sql`, datos reales)

```text
 mensajes recibidos por resultado (attempt = 0, sin sintéticos): new 32.976 · revised 134 · quarantined 2
 reprocesados (attempt = 1): new 1 · revised 1
 received 33.112 · sum_of_outcomes 33.112 · difference 0
 cuarentena real por motivo: magnitude_out_of_range 2
 eventos reales por marca: (ninguna)
 completitud sobre 32.977 terremotos actuales: magnitud 100 % · tipo de magnitud 100 % · profundidad 100 %
 versiones distintas 33.112 = mensajes 33.112 · versiones duplicadas 0 · identificadores repetidos 0
 coordenadas inválidas 0 · updated_at anterior a event_time 0 · países fuera de la dimensión 0
 retraso ocurrencia → actualización en USGS: mediana 109.178 min (≈ 76 días) · p95 130.843 min
 retraso ocurrencia → ingesta: mediana 523.735 min (≈ 364 días) · p95 934.063 min
```

Los dos retrasos están dominados por el histórico (2025 y 2026 cargados con el catálogo): no
miden la latencia del feed. La memoria los separa por procedencia.

Variantes solo sintéticas (separadas de lo anterior):

```text
 mensajes sintéticos: new 1.013 · excluded 2 · quarantined 16 (1.031 en total)
 eventos sintéticos por marca: synthetic 1.013 · depth_from_text 1 · depth_not_numeric 1 ·
   depth_out_of_range 1 · extra_coordinates 1 · future_time 1 · magnitude_from_text 1 ·
   magnitude_not_numeric 1 · magnitude_out_of_range 1 · negative_depth 1 · updated_before_time 1
 cuarentena sintética por motivo: 15 códigos distintos (un mensaje con dos motivos cuenta una sola
   vez como rechazado y una vez en cada motivo)
 completitud sintética: magnitud 99,80 % (1.011 de 1.013; dos magnitudes nulas a propósito)
```
