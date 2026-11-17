# W16: identidad y contraste

Fecha: 2026-11-17.

- **Nombre y título**: la cabecera muestra «seismicobservatory» con el logotipo «S» con onda sísmica; `<title>` es «seismicobservatory»; favicon `brand/favicon.svg`; `meta theme-color` oscuro (`#0b1520`) y claro (`#eef3f6`) ([oscuro](panel-dark.png), [claro](panel-light.png)). Tipografía del sistema, sin fuentes externas.
- **Logotipo provisional**: sigue pendiente de aprobación de la usuaria (FR-018).

## Contraste

Medido con la fórmula WCAG de luminancia relativa sobre los tokens de `frontend/src/styles.css`.

| Elemento | Antes (colores de `geo.ts`) | Ahora (tokens por tema) |
|---|---|---|
| Profundidad «profunda» en oscuro | 2,56:1 (insuficiente, < 3:1) | `#a97be0` sobre `#121f2d`: 5,24:1 |
| Profundidad «superficial» en claro | 2,17:1 (insuficiente) | `#b87800` sobre `#ffffff`: 3,67:1 |
| Resto de pares de profundidad | | entre 3,67:1 y 9,32:1 |
| Texto principal | | 14,26:1 (oscuro) y 14,51:1 (claro) |
| Texto secundario | | 8,30:1 (oscuro) y 7,30:1 (claro) |
| Acento | | 8,94:1 (oscuro) y 6,24:1 (claro) |

Corrección aplicada: la función `depthColor(clave, tema)` de `lib/map-layers.ts` da el color de profundidad según el tema y la usan el mapa (círculos), la leyenda y el gráfico de profundidad, de modo que los tres coinciden. Los colores de `geo.ts` no se modificaron.

axe-core (WCAG 2.0 y 2.1, A y AA) tras el cambio: 0 violaciones en oscuro y en claro ([w-smoke.json](w-smoke.json)).

Límite: los círculos del mapa se dibujan sobre teselas de colores variables; el contraste se midió contra la superficie del panel, no contra cada tesela. El borde del círculo y el tamaño mantienen la información sin depender solo del color.
