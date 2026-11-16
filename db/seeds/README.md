# Carpeta `db/seeds`

Esta carpeta ya no contiene lotes versionados en Git. Se mantiene solo como marcador (`.gitkeep`)
y este README.

## Por qué no hay lotes aquí

- Los conjuntos descargados de USGS no se guardan en Git: son regenerables con el procedimiento
  de la spec 003 y versionarlos mezclaría datos externos con el código.
- Los casos de prueba de reproducción los genera el código, no ficheros fijos. El conjunto
  sintético lo produce `producer/app/replay/synthetic.py`, con la convención de la spec 004 y
  resultados esperados comprobables.
- Así hay un único mecanismo de reproducción, en vez de dos con resultados distintos.

Los ficheros `historical_1900.jsonl` e `historical_2025.jsonl` se han retirado de Git por esas
razones.

## Conjuntos descargados: en `data/`, fuera de Git

Las descargas (por ejemplo, el histórico mundial de 2025 con magnitud ≥ 4 que exige el enunciado)
van en `data/`, que está en `.gitignore` y que Compose monta en solo lectura en `/data` en
productor y consumidor. Ninguna imagen de Docker las contiene.

Para regenerarlas:

```
docker compose run --rm catalog-loader
```

El procedimiento y su registro en la base están en el apartado «Cargar el histórico» del
[README](../../README.md#cargar-el-histórico) y en el contrato
[catalog-loader.md](../../specs/003-usgs-ingestion/contracts/catalog-loader.md) (spec 003).
La base registra cada consulta en `core.extraction` y la huella SHA-256 y la ruta del fichero en
`core.raw_payload`, de modo que se puede comprobar que el fichero usado es el descargado.

## Cómo se reproduce ahora

El escenario de reproducción histórica y sus comprobaciones están en el
[quickstart de la spec 005](../../specs/005-historical-replay/quickstart.md).

## Copias de seguridad

No deben guardarse copias (`*.bak`, `*.orig`) en esta carpeta.
