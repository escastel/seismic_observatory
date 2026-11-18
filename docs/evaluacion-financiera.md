# Evaluación financiera

**Revisada en la spec 008 frente al principio IX de la constitución** («los costes distinguen valores medidos de supuestos y no
inventan beneficios económicos; un ROI solo se estima si se define un beneficio medible y justificable»). Cálculo completo y
supuestos en [evidence/008/cost-table.md](evidence/008/cost-table.md).

## Qué se retiró y por qué

La versión anterior daba un VAN de 10.730,74 € y una TIR del 38,5 % con una inversión de 12.000 € y flujos de 5.000 a 7.000 € al
año que **no tenían supuesto trazable** (ni ingreso, ni ahorro, ni partida de la que salieran). Se retiraron esos flujos y ese
veredicto. Lo que sigue los sustituye por costes y un beneficio con origen declarado.

## Costes (cinco años, tasa de descuento supuesta del 10 %)

| Concepto | Cálculo | Importe | Tipo |
|---|---|---:|---|
| Desarrollo | 200 h × 15 €/h (horas y tarifa de la persona autora) | 3.000 € (una vez) | supuesto |
| Hardware | portátil de 675 € a 6 años de vida | 112,50 €/año | supuesto |
| Electricidad | 35 W × 8.760 h × 0,23 €/kWh | 70,52 €/año | supuesto (la potencia no está medida) |
| Mantenimiento | 2 h/mes × 15 €/h | 360 €/año | supuesto |
| Almacenamiento, transferencia | 0,29 € una vez; dentro de las cuotas gratuitas | ≈ 0 € | medida × supuesto |
| **Recurrente** | | **543,02 €/año** | |
| **Valor actual de los costes a 5 años** | 3.000,29 + 543,02 × 3,7908 | **5.058,8 €** | |

## Beneficio y ROI

El observatorio no genera ingresos. El único beneficio que se define es **el tiempo de trabajo manual evitado**: sin el panel habría
que descargar y filtrar a mano el catálogo de USGS para obtener una vista equivalente (recuento por país, distribuciones y comparación
con 2025).

- **Definición (de la persona autora)**: 2 horas por consulta, una consulta por día laborable (260 al año), valoradas a 15 €/h
  → **7.800 €/año**.
- **Justificación y límite**: es un coste de oportunidad del tiempo propio, no un ahorro de caja, y descansa en dos estimaciones
  **no medidas** (las 2 horas y la frecuencia diaria). Para respaldarlo mejor, cronometrar una vez la consulta manual y anotar
  cuántas veces se usa el panel de verdad.

| Resultado (5 años, 10 %) | Valor |
|---|---:|
| Valor actual del beneficio (7.800 × 3,7908) | 29.568,1 € |
| **VAN** (beneficio − costes) | **24.509,4 €** |
| **ROI descontado** (VAN / valor actual de los costes) | **484,5 %** |
| ROI sin descontar | 582,4 % |
| Beneficio anual mínimo para VAN = 0 | 1.334,5 €/año (≈ 0,86 consultas de 2 h por semana) |

**Sensibilidad**: con una consulta semanal (1.560 €/año) el VAN es 854,9 €, apenas positivo; con una mensual (360 €/año) es
−3.694,1 €. La conclusión «el observatorio compensa» **solo se sostiene si se usa al menos una vez por semana** el equivalente de
la consulta manual. Si cambian los supuestos, el resultado debe recalcularse y no heredarse.
