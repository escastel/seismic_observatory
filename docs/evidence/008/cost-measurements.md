# Medidas para el informe de costes (T017)

**Fecha**: 2026-11-17 14:39–14:45 UTC · Equipo y stack de [00-environment.md](00-environment.md). Todo lo de este fichero es
**medida** (no supuesto), salvo donde se indica «derivado».

## Almacenamiento

| Concepto | Medido |
|---|---|
| Base de datos PostgreSQL (`pg_database_size`) | 83 MB (87.544.291 bytes) |
| `core.event_version` / `core.event_current` / `core.message_log` / `core.raw_payload` | 39 MB / 12 MB / 5,6 MB / 4,5 MB (275 originales comprimidos; 4.189 kB de cuerpo) |
| Volumen Docker `postgres_data` (`docker system df -v`) | 195 MB |
| Datos de topics de Kafka (`du` en `/var/lib/kafka/data`) | 108 MB: `earthquakes.catalog-0` 53 MB, `earthquakes.replay-0` 38 MB, `earthquakes.live-0` 2,1 MB, metadatos 6,6 MB |
| Volumen Docker `kafka_data` (`docker system df -v`) | 1,244 GB **aparentes**; en disco 108–110 MB (`du` 110.048 KB; `du --apparent-size` 1.214.992 KB). La diferencia son los ficheros `.index` y `.timeindex` dispersos de 10 MB por partición (56 particiones). Retención `KAFKA_RETENTION_HOURS` = 168 h |
| Panel compilado (`frontend/dist/observatorio/browser`) | 1.222 kB; `frontend/public/datos` (polígonos de países) 820 kB |
| Contenido de la base | 34.207 eventos reales y sintéticos en `core.event_current`; 2.807 en `replay` |

## Memoria y CPU en reposo (`docker stats`, una muestra)

kafka 879 MiB · consumer 82 MiB · api 48 MiB · postgres 46 MiB · producer 37 MiB · tunnel 15 MiB (suma ≈ 1,1 GiB de
los 7,6 GiB visibles para Docker). CPU de los servicios por debajo del 6 % (la muestra se tomó con una medición en marcha).

## Transferencia de la API (bytes de respuesta, sin compresión: la API no comprime)

| Petición | Bytes |
|---|---:|
| `GET /api/eventos` (24 h por defecto, 169 eventos en ese instante) | 59.238 |
| `GET /api/estadisticas` (24 h) | 2.675 |
| `GET /api/salud` | 111 |
| `GET /api/eventos?limit=1000` sobre 2025 con `min_mag=4` (1.000 eventos) | 307.772 |
| `GET /api/estadisticas` de 2025 con `min_mag=4` | 304.367 |

**Derivado** (cálculo, no medida): una pestaña abierta con el periodo por defecto hace 3 peticiones por minuto
(eventos, estadísticas y salud, 62.024 bytes por refresco): 1.440 refrescos al día → ≈ 89,3 MB/día ≈ 2,7 GB al mes
si estuviera abierta de forma continua. La carga inicial del panel descarga además ≈ 1,2 MB de la SPA desde Netlify.

## Uso real de ngrok este mes (conector de ngrok, `platform_get_limits`, 2026-11-17)

- Transferencia de salida del mes natural en curso (1–17 nov): **191.053.586 bytes** (≈ 191 MB; tope del plan 1.000.000.000).
- Peticiones HTTP que han llegado al upstream este mes: 5.282. Endpoints concurrentes: 1 de 3. Conexiones simultáneas: 1 de 100.
- Derivado: 191 MB / 17 días ≈ 11,2 MB/día ≈ 337 MB al mes con el uso de desarrollo y pruebas hecho hasta ahora.

## Nota posterior (2026-11-17, tras las mediciones de escala)

El volumen `postgres_data` pasó de 195 MB a 1,18 GB después de cargar dos veces 1.000.000 de filas sintéticas en `bench`: `pg_wal` ocupa 1,1 GB
(`max_wal_size` = 1 GB) y `base/` 104 MB; la base sigue en 82 MB. Son segmentos de WAL reciclados, no datos: el tamaño queda acotado por `max_wal_size`.
Las partidas de coste se actualizaron después con los valores de la usuaria (ver [cost-table.md](cost-table.md)); esta nota no cambia ningún importe.
