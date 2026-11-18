# Modelo de datos (Fase 1)

No hay tablas nuevas en `core` ni `replay`. El esquema `bench` es efímero (002) y se elimina al
terminar. Las entidades siguientes son estructuras de documentación y de salida de medición.

## Conclusión
| Campo | Descripción |
|---|---|
| id | `C1`, `C2`, … |
| enunciado | afirmación sin predicción ni riesgo |
| cifras | valores con unidad |
| periodo | inicio inclusivo, fin exclusivo, UTC |
| filtros | `min_mag`, tipo, `country_id`, modo (real) |
| sin_valor | registros sin magnitud o profundidad excluidos |
| consulta | llamada a la API o SQL que la regenera |
| ejecutada_en | instante UTC de ejecución |
| captura | fichero en `docs/evidence/008/` con los mismos filtros |
| avisos | periodo reciente incompleto; cobertura y tipos de magnitud |

## Medición
`operacion`, `variante` (secuencial, diccionario, consulta sin índice, con índice, etc.), `n`
(10.000 / 100.000 / 1.000.000), `mediana_ms`, `pico_memoria_mib`, `repeticiones`, `equipo`,
`versiones`, `tipo` = medida. Salida JSON + Markdown en `docs/evidence/008/`.

## Supuesto
`nombre`, `valor`, `unidad`, `fuente_o_razon`, `fecha`, `tipo` = supuesto. Nunca se mezcla con
una Medición en la misma celda.

## Partida de coste
`concepto` (hardware, electricidad, almacenamiento, transferencia, mantenimiento, desarrollo),
`importe`, `periodo`, `tipo` (medida | supuesto), `referencia` (evidencia o supuesto).

## Entrada de trazabilidad
`eje` (§11 | §12 | §13), `elemento`, `destino` (spec, evidencia, fichero o sección), `estado`
(superada con evidencia | parcial | pendiente de la persona autora), `hueco` (qué falta y cómo se
demuestra).

## Hueco
`id`, `quien` (persona autora), `equipo` (Linux | otro dispositivo), `procedimiento`, `evidencia_esperada`.
