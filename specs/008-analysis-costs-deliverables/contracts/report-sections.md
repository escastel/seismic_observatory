# Contrato de contenido de la memoria (008)

Las entregas de esta feature son apartados de `docs/report.md` (y ficheros de `docs/`). Cada
apartado cumple lo siguiente; es el criterio de revisión de la matriz y de las pruebas.

## Análisis
- ≥ 3 conclusiones, cada una con: cifras y unidad, periodo (inicio inclusivo, fin exclusivo, UTC),
  filtros exactos, registros sin valor, captura del panel, consulta o llamada de regeneración,
  instante de ejecución, avisos (periodo reciente incompleto; cobertura y tipos de magnitud).
- Comparaciones: mismos filtros en ambos periodos; denominador con días sin eventos; ND si media 0.
- Sin predicción ni riesgo. Reproducción y sintéticos fuera; reproducción, si aparece, aparte y
  con la etiqueta «REPRODUCCIÓN».

## Complejidad y rendimiento
- Por operación: estructura, coste medio, peor caso, justificación.
- Tabla de medidas: operación × variante × tamaño (≥ 3) × tiempo × memoria; equipo y procedimiento.
- Medidas y supuestos en tablas o columnas separadas. 100 M: razonamiento marcado como supuesto.
- La medición de índices de la 002 se cita por enlace, no se repite.

## Costes
- Partidas: hardware, electricidad, almacenamiento, transferencia, mantenimiento, desarrollo.
- Cuotas gratuitas: límite y consecuencia de superarlo, con fecha de consulta.
- ROI: solo con beneficio medible y justificable; si no, «no estimado» y por qué.
- Propuesta de escalado y mejoras.

## Matrices
- §11: 11 filas (prueba → spec → evidencia → estado → hueco).
- §12: entregable → fichero.
- §13: criterio → sección.
- Estado «superada» solo con evidencia esperado/observado en `docs/evidence/`.
