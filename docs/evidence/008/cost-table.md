# Tabla de partidas de coste (T019)

**Fecha**: 2026-11-17. Las columnas separan lo **medido** (enlace a evidencia) de lo **supuesto** (valor y razón). Los supuestos
son valores de trabajo editables por la usuaria; **ninguno procede de una medición**. Medidas: [cost-measurements.md](cost-measurements.md)
y [free-tier-limits.md](free-tier-limits.md).

## Supuestos

| Id | Supuesto | Valor | Razón |
|---|---|---|---|
| S1 | Precio de compra del equipo | 900 € | orden de magnitud de un portátil de gama media como el usado (i5-11400H, 16 GB); **no es el precio real pagado** |
| S2 | Vida útil para amortizar | 4 años (lineal) | convención habitual; el equipo se imputa al 100 % al proyecto (cota superior: es de uso general) |
| S3 | Potencia media adicional del stack | 35 W | **no medida**: se supone para una carga ligera continua (Kafka, PostgreSQL, tres procesos Python); medirla requiere un vatímetro |
| S4 | Tarifa eléctrica | 0,20 €/kWh | orden de magnitud doméstico; no consultada a una comercializadora |
| S5 | Horas de funcionamiento | 8.760 h/año (24/7) | escenario más caro; la defensa solo exige horas de demostración |
| S6 | Coste del almacenamiento local | 0,20 €/GB | SSD de ≈ 100 € por 512 GB |
| S7 | Mantenimiento | 2 h/mes a 20 €/h | revisar el stack, rotar el túnel y actualizar imágenes |
| S8 | Desarrollo | 100 h a 20 €/h | **la usuaria debe sustituir por sus horas reales** |
| S9 | Tasa de descuento | 10 % | la que usaba la evaluación anterior; sin fuente, se mantiene solo como parámetro |

## Partidas

| Partida | Cálculo | Importe | Tipo |
|---|---|---:|---|
| Hardware | S1 / S2 | 225 €/año | supuesto |
| Electricidad | S3 × S5 × S4 = 0,035 kW × 8.760 h × 0,20 €/kWh | 61,32 €/año (5,04 €/mes) | supuesto |
| Almacenamiento | volúmenes medidos 1,44 GB (195 MB + 1,244 GB aparentes de Kafka; en disco ≈ 0,3 GB, así que es una cota superior) × S6 | 0,29 € (una vez; crece con el histórico) | medida × supuesto |
| Transferencia | 191 MB este mes de 1 GB incluido en ngrok; la SPA en Netlify cuesta créditos de una cuota de 300 | 0 € dentro de cuota | medida de uso + cuota publicada |
| Mantenimiento | S7 = 2 × 12 × 20 | 480 €/año | supuesto |
| Desarrollo | S8 = 100 × 20 | 2.000 € (una vez) | supuesto |
| **Recurrente** | 225 + 61,32 + 480 | **766,32 €/año** | |
| **Total del primer año** | recurrente + 2.000 + 0,29 | **2.766,61 €** | |

**Valor actual de los costes a 5 años** (S9): 2.000 + 0,29 + 766,32 × 3,7908 = **4.905,2 €** (sin descontar: 5.831,9 €).
**Beneficio anual mínimo para que el valor actual neto sea 0**: 4.905,2 / 3,7908 = **1.294,0 €/año**. Es el umbral que habría
que demostrar con un beneficio medible; el observatorio no define ninguno, por lo que el ROI no se estima.
