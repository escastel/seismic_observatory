# Distancia a tierra de los eventos «Sin país asignado» (seguimiento de C1)

**Ejecución**: 2026-11-17 18:01 UTC · Script [tests/analysis/coastal_distance.py](../../../tests/analysis/coastal_distance.py) (solo lectura, esquema `core`, sin sintéticos) · Salida literal:
[coastal-distance.out](coastal-distance.out). **No asigna ningún país**: solo mide a qué distancia de tierra caen los eventos que no tienen país.

**Conjunto**: 14.350 eventos reales de 2025 con magnitud ≥ 4 y sin país (los mismos de C1). Polígonos: 177 entidades de Natural Earth con 10.642 vértices exteriores en total
(60 de media por entidad: contorno muy simplificado). Distancia: círculo máximo (km) al punto más cercano del polígono más próximo; el punto más cercano se busca en longitud/latitud planas
(pequeño error en latitudes altas) y se prueba también con la longitud desplazada ±360° por el antimeridiano.

| Distancia a tierra (km) | Eventos | % | % acumulado |
|---|---:|---:|---:|
| 0–10 | 412 | 2,9 | 2,9 |
| 10–50 | 1.853 | 12,9 | 15,8 |
| 50–100 | 2.526 | 17,6 | 33,4 |
| 100–200 | 3.758 | 26,2 | 59,6 |
| 200–500 | 2.441 | 17,0 | 76,6 |
| ≥ 500 | 3.360 | 23,4 | 100,0 |

Mediana 144,4 km; cuartiles 78,1 y 455,9 km; percentil 95: 1.863,5 km; máximo 4.303,0 km.

**Lectura**:
- El 15,8 % (2.265 eventos) está a menos de 50 km de tierra: es el grupo en el que el contorno simplificado puede dejar fuera de un país un evento de costa o de aguas cercanas.
- La mayoría (59,6 %) está a más de 100 km y casi una cuarta parte (23,4 %) a más de 500 km: son eventos de mar abierto o de dorsales y fosas lejanas a la costa, que ningún polígono de tierra cubriría.
- Por tanto «Sin país asignado» es **sobre todo mar**, no un artefacto de la resolución del mapa; el artefacto afecta como mucho a un 16 % del grupo (≈ 12,4 % del total de eventos de M ≥ 4 de 2025: 2.265 de 18.302).
- **Límite**: la distancia al polígono no dice a qué país pertenece el evento y no debe usarse para asignarlo (constitución IV). Una advertencia de ejecución de Shapely (`invalid value in shortest_line`) apareció en alguna de las
  pruebas desplazadas ±360°; no hay ningún evento sin distancia finita (máximo 4.303 km).
