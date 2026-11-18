# Tabla de partidas de coste y ROI (T019, actualizada el 2026-11-17 con los datos de la persona autora)

Las columnas separan lo **medido** (enlace a evidencia) de lo **supuesto** (valor y razón). Medidas: [cost-measurements.md](cost-measurements.md)
y [free-tier-limits.md](free-tier-limits.md). Los valores S1, S2, S4, S7 y S8 **los dio la persona autora** (se indica); S3, S5, S6 y S9 siguen siendo
supuestos del autor; S10 a S12 definen el beneficio del ROI y también son de la persona autora. Ninguno procede de una medición.

## Supuestos

| Id | Supuesto | Valor | Origen y razón |
|---|---|---|---|
| S1 | Precio de compra del portátil | 675 € | la persona autora: comprado hace 4 años |
| S2 | Vida útil total para amortizar | 6 años (lineal, 112,50 €/año) | la persona autora: «todavía puedo sacarle rentabilidad»; se imputa al 100 % al proyecto (cota superior: es de uso general) |
| S3 | Potencia media adicional del stack | 35 W | autor; **no medida** (haría falta un vatímetro) |
| S4 | Tarifa eléctrica | 0,23 €/kWh | la persona autora |
| S5 | Horas de funcionamiento | 8.760 h/año (24/7) | autor; escenario más caro: la defensa solo exige unas horas |
| S6 | Coste del almacenamiento local | 0,20 €/GB | autor; SSD de ≈ 100 € por 512 GB |
| S7 | Mantenimiento | 2 h/mes a 15 €/h | la persona autora |
| S8 | Desarrollo | 200 h a 15 €/h | la persona autora: «unas 200 h» (estimación, no cronometradas) |
| S9 | Tasa de descuento | 10 % | la de la evaluación anterior; sin fuente, solo como parámetro |
| S10 | Beneficio: tiempo manual evitado por consulta | 2 h | la persona autora: hacer a mano una vista equivalente a la del panel descargando y filtrando el catálogo de USGS (estimación, **no cronometrada**) |
| S11 | Frecuencia de esa consulta sin observatorio | 1 por día laborable = 260/año | la persona autora |
| S12 | Valor de la hora evitada | 15 €/h | la misma tarifa que S7 y S8 |

## Partidas de coste

| Partida | Cálculo | Importe | Tipo |
|---|---|---:|---|
| Hardware | S1 / S2 = 675 / 6 | 112,50 €/año | supuesto |
| Electricidad | S3 × S5 × S4 = 0,035 kW × 8.760 h × 0,23 €/kWh (306,6 kWh) | 70,52 €/año (≈ 5,8 €/mes) | supuesto |
| Almacenamiento | volúmenes medidos 1,44 GB (cota superior, ver [cost-measurements.md](cost-measurements.md)) × S6 | 0,29 € (una vez) | medida × supuesto |
| Transferencia | 191 MB este mes de 1 GB incluido en ngrok; la SPA en Netlify cuesta créditos de una cuota de 300 | 0 € dentro de cuota | medida de uso + cuota publicada |
| Mantenimiento | S7 = 2 × 12 × 15 | 360 €/año | supuesto |
| Desarrollo | S8 = 200 × 15 | 3.000 € (una vez) | supuesto |
| **Recurrente** | 112,50 + 70,52 + 360 | **543,02 €/año** | |
| **Total del primer año** | recurrente + 3.000 + 0,29 | **3.543,31 €** | |

**Valor actual de los costes a 5 años** (S9, factor de anualidad 3,7908): 3.000 + 0,29 + 543,02 × 3,7908 = **5.058,8 €**
(sin descontar: 5.715,4 €). Lo dominante es el trabajo humano (3.360 € del primer año de 3.543,31 €).

## ROI (con el beneficio definido en S10 a S12)

| Concepto | Cálculo | Importe |
|---|---|---:|
| Beneficio anual | S10 × S11 × S12 = 2 h × 260 × 15 €/h | 7.800 €/año |
| Valor actual del beneficio a 5 años | 7.800 × 3,7908 | 29.568,1 € |
| Valor actual neto (VAN) | 29.568,1 − 5.058,8 | **24.509,4 €** |
| ROI descontado | VAN / valor actual de los costes = 24.509,4 / 5.058,8 | **484,5 %** |
| ROI sin descontar | (7.800 × 5 − 5.715,4) / 5.715,4 | 582,4 % |
| **Beneficio anual mínimo para VAN = 0** | 5.058,8 / 3,7908 | **1.334,5 €/año** (89 h/año ≈ 44,5 consultas de 2 h ≈ 0,86 por semana) |

**Sensibilidad a la frecuencia (S11)**, con S10 = 2 h y S12 = 15 €/h:

| Frecuencia | Beneficio anual | VAN a 5 años |
|---|---:|---:|
| Diaria (260/año) | 7.800 € | 24.509,4 € |
| Semanal (52/año) | 1.560 € | 854,9 € |
| Mensual (12/año) | 360 € | −3.694,1 € |

**Cautelas**: el beneficio descansa en dos estimaciones no medidas (2 h por consulta y una consulta diaria) y valora el tiempo propio a 15 €/h; no es un ingreso
ni un ahorro de caja. Para justificarlo mejor, cronometrar una vez la consulta manual con el catálogo y anotar con qué frecuencia se usa realmente el panel. Con una
frecuencia semanal el VAN es apenas positivo y con una mensual es negativo.
