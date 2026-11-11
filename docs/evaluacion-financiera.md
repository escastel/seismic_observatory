# Evaluación financiera

La evaluación usa un horizonte de cinco años y no utiliza ROI simple como criterio
de decisión. Los valores siguientes son supuestos académicos explícitos para
comparar la alternativa local con una operación manual.

| Año | Flujo neto (€) |
|---:|---:|
| 0 | -12000 |
| 1 | 5000 |
| 2 | 5500 |
| 3 | 6000 |
| 4 | 6500 |
| 5 | 7000 |

Supuestos: inversión inicial de 12.000 €, tasa de descuento/WACC del 10% y
flujos netos ya descontados de costes operativos locales. Con esos supuestos:

```text
NPV = -12000 + 5000/1.10 + 5500/1.10^2 + 6000/1.10^3
      + 6500/1.10^4 + 7000/1.10^5 = 10.730,74 €
IRR ≈ 38,5 %
WACC = 10 %
```

La alternativa es viable bajo estos supuestos porque `NPV > 0` e `IRR > WACC`.
Si cambian los costes, beneficios o tasa de descuento, el veredicto debe
recalcularse y no heredarse automáticamente.
