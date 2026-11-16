# Evidencias de la spec 004: consumidor y calidad de los datos

Resultados de los escenarios de [quickstart.md](../../../specs/004-consumer-quality/quickstart.md),
observados el 2026-11-16 entre las 13:00Z y las 14:10Z en Windows 11 Pro for Workstations con
Docker Desktop 29.1.3 (motor con 12 CPU y 7,6 GiB), sobre el sistema real salvo donde se indica.
Ningún escenario se marca como superado sin haberlo ejecutado; cada fichero enlazado incluye la
orden, la cabecera de equipo y commit, y la salida.

| Escenario | Esperado | Observado | Resultado | Evidencia |
|---|---|---|---|---|
| V1 · Cada regla a su destino | Cada caso acaba donde dice el catálogo; magnitud nula, negativa, profundidad negativa y evento antiguo: 0 en cuarentena | 65 casos unitarios y 41+ pruebas de base de datos en verde; 31 mensajes sintéticos con el sistema real: 13 eventos, 16 cuarentena, 2 exclusiones | SUPERADA | [tests.txt](tests.txt), [acceptance.md](acceptance.md) |
| V2 · Pruebas de aceptación §11 | Magnitud nula conservada, coordenadas inválidas a cuarentena, evento marítimo sin país en el análisis | Las tres comprobadas con casos sintéticos en el sistema real; repetir la inyección: «Publicados 0, omitidos 31» | SUPERADA | [acceptance.md](acceptance.md) |
| V3 · Reiniciar el consumidor | Mismos recuentos que sin reinicio | Muerto tras 357 de 1.000; al reiniciar terminó: 1.000 eventos, 1.000 versiones, 1.000 mensajes, offsets 610–1609 sin huecos | SUPERADA | [restart.md](restart.md) |
| V4 · Reprocesado | Recupera lo rechazado por reglas retiradas, idempotente, sin borrar | 2 filas reales recuperadas (magnitud −0,02), 16 sintéticas siguen rechazadas, segunda ejecución sin cambios | SUPERADA | [reprocess.md](reprocess.md) |
| V5 · País | Determinista, unicidad comprobada, sin país en el mar | Pruebas en verde; recalculados los 32.977 eventos reales: 0 cambian de país, 0 ambiguos | SUPERADA | [spatial-and-counts.md](spatial-and-counts.md) |
| V6 · Recuentos | recibidos = suma de resultados, diferencia 0 | 33.112 = 33.112; 22 consultas sin errores | SUPERADA | [spatial-and-counts.md](spatial-and-counts.md) |
| V7 · Sintéticos aparte | 0 filas sintéticas en las consultas reales; todas identificadas | Cuarentena real: 2 filas; 16 sintéticas marcadas (tras corregir el marcado por clave, ver abajo); variantes `-synthetic-only` | SUPERADA | [acceptance.md](acceptance.md) |
| V8 · Calidad en la memoria | Seis dimensiones con consulta, denominador, resultado, acción y limitación | Apartado «Calidad de los datos» de `docs/report.md`; consultas repetidas con su salida | SUPERADA | [quality-queries.md](quality-queries.md) |
| V9 · Nada fuera de alcance | Suite en verde; sin cambios en productor, API, panel ni `common/` | 515 pruebas superadas; `git diff 003-usgs-ingestion` vacío en esas rutas | SUPERADA | [tests.txt](tests.txt) |
| Migración `041` | Sobre la base existente, dos veces, sin perder filas | Aplicada dos veces; 33.112 filas conservadas | SUPERADA | [acceptance.md](acceptance.md) |

## Hallazgo durante la validación

Los mensajes sintéticos con JSON ilegible (`malformed_json`, `not_an_object`) quedaron sin marcar
como sintéticos y entraban en los recuentos reales. Se corrigió haciendo que una **clave de Kafka**
con el prefijo reservado `synthetic-` marque el mensaje aunque su cuerpo no se pueda leer. Está
detallado, con su prueba, en [acceptance.md](acceptance.md).

## Revisión constitucional (v2.1.0)

| Principio | Estado al cerrar la 004 |
|---|---|
| II. Al menos una vez, idempotente | Cumple: transacción por mensaje, offset tras el commit y reintento del mismo mensaje se mantienen; reiniciar a mitad de lote deja los mismos recuentos (V3); el reprocesado es idempotente |
| III. Calidad | **Cumple; cierra la desviación abierta desde la spec 002.** Los nulos se conservan, los valores negativos no se rechazan, las anomalías se señalan, solo va a cuarentena lo intratable con todos los motivos y el original, las exclusiones conservan el motivo y ningún mensaje defectuoso bloquea la cola |
| IV. Integración espacial | Cumple: punto en polígono en EPSG:4326, `ADM0_A3` único comprobado al arrancar, regla determinista y documentada, «Sin país asignado» sin error |
| V. Original y procedencia | Cumple: el original sigue íntegro en `event_version.payload` y en la cuarentena; el reprocesado conserva la fila original |
| VI. Aislamiento de la reproducción | Cumple: mismas reglas en los tres topics; el reprocesado escribe en el esquema que indica el topic de cada fila |
| VII. Analítica desde el estado actual | Cumple: los recuentos salen solo de SQL sobre lo almacenado, con denominador, sin contadores y sin sintéticos |
| VIII. Contrato de la API | Sin cambios; la magnitud nula llega nula y contada para la spec 006. **Sigue abierta** la desviación de esta spec |
| IX. Evidencia ejecutada | Cumple: esta tabla, con salida guardada de cada escenario y casos sintéticos identificados |
| Idioma y repositorio público | Cumple: códigos de motivo y marcas en inglés, documentación en español; ningún dato descargado en Git; `scan-evidence.sh` limpio |

Modelo: tres cambios aditivos justificados (columnas de reprocesado, `attempt` en el registro de
mensajes y el resultado `excluded`), documentados en el diccionario de datos y en el contrato de
base de datos de la spec 002. Sigue abierta la desviación del principio VIII (spec 006); mientras
exista, la rama no se fusiona en `main`.
