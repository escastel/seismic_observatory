# Evaluación financiera

**Revisada en la spec 008 frente al principio IX de la constitución** («los costes distinguen valores medidos de supuestos y no
inventan beneficios económicos; un ROI solo se estima si se define un beneficio medible y justificable»).

## Qué se ha retirado y por qué

La versión anterior calculaba un VAN de 10.730,74 € y una TIR del 38,5 % a cinco años con una inversión de 12.000 € y flujos
netos de 5.000 a 7.000 € al año. Esos importes **no tenían supuesto trazable**: no había ingreso, ahorro ni coste del que
salieran, y la inversión de 12.000 € no corresponde a ninguna partida del proyecto. Un observatorio académico que corre en un
portátil no genera ingresos. Se retiran los flujos, el VAN, la TIR y el veredicto «viable».

## Qué se mantiene: los costes, con supuestos explícitos

Los costes (hardware, electricidad, almacenamiento, transferencia, mantenimiento y desarrollo) están en la sección «Costes» de
[report.md](report.md) y en [evidence/008/cost-table.md](evidence/008/cost-table.md), con cada valor marcado como medida o
supuesto. Resumen a cinco años con una tasa de descuento supuesta del 10 %:

| Concepto | Importe | Tipo |
|---|---:|---|
| Coste recurrente anual (hardware amortizado, electricidad 24/7, mantenimiento) | 766,32 €/año | supuesto |
| Desarrollo y almacenamiento inicial | 2.000,29 € | supuesto (las horas debe confirmarlas la usuaria) |
| Valor actual de los costes a 5 años | 4.905,2 € | supuesto |

## ROI: no se estima

El observatorio no tiene un beneficio económico medible y justificable definido, así que **no se calcula ROI, VAN ni TIR**. Lo que
sí se puede afirmar sin inventar nada es el umbral: para que el valor actual neto fuera 0 haría falta un beneficio de
**1.294,0 €/año** durante cinco años. Un beneficio válido tendría que:

1. definirse con una unidad medible (por ejemplo, horas de trabajo manual evitadas por mes), y
2. justificarse con una medición o una fuente (cuánto tarda hoy el procedimiento alternativo, quién lo hace y cuánto cuesta esa hora).

Si la usuaria define ese beneficio, se recalcula con la fórmula `VAN = −costes_iniciales + Σ (beneficio_t − costes_t) / (1 + r)^t`
y el veredicto no se hereda de esta versión.
