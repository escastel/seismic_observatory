# Lotes de reproducción versionados

Esta carpeta contiene solo lotes pequeños que se versionan en Git porque las pruebas y la
demostración los necesitan siempre igual. Compose la monta en solo lectura en `/seeds` dentro
del productor.

| Fichero | Contenido | Líneas |
|---|---|---|
| `historical_2025.jsonl` | Seis eventos **ficticios** de enero de 2025: válidos, uno marítimo, rechazos de calidad y dos versiones del mismo identificador. No es una descarga de USGS | 6 |
| `historical_1900.jsonl` | Año 1900 completo según la API de USGS (el primero de su catálogo), extraído el 2026-11-11 UTC. SHA-256 `95F0BE1FC5D23ECDAE67D885DA75BCF6EFDB110A44BC11BE842C26BD99163927` | 35 |

Formato: un objeto GeoJSON `Feature` por línea, con `id`, `time` y `updated` copiados también
al primer nivel para el publicador de `producer/app/replay.py`.

## Conjuntos descargados: en `data/`, fuera de Git

Las descargas grandes (por ejemplo, el histórico mundial de 2025 con magnitud ≥ 4 que exige el
enunciado) no se guardan aquí ni en ningún otro lugar del repositorio:

- se guardan en `data/`, que está en `.gitignore` y que Compose monta en solo lectura en
  `/data` en productor y consumidor;
- ninguna imagen de Docker los contiene;
- la base registra cada consulta en `core.extraction` y la huella SHA-256 y la ruta del fichero
  en `core.raw_payload` (con `encoding = 'file'`), de modo que se puede comprobar que el
  fichero usado es el mismo que se descargó.

El procedimiento de descarga, la regeneración de los ficheros y su registro en la base están
en el apartado «Cargar el histórico» del [README](../../README.md#cargar-el-histórico) y en
[contracts/catalog-loader.md](../../specs/003-usgs-ingestion/contracts/catalog-loader.md)
(spec 003): `docker compose run --rm catalog-loader`. El renombrado de `historical_2025.jsonl`, que hoy contiene eventos
ficticios, y el marcado de los casos sintéticos se deciden en la spec 005.

Ninguna copia (`*.bak`, `*.orig`) debe quedar en esta carpeta.
