# Contrato de ejecución: cambios sobre la spec 002

Amplía [contracts/runtime.md de la spec 002](../../002-platform-data-model/contracts/runtime.md).
Lo que no aparece aquí no cambia.

## Servicios

| Servicio | Cambio |
|---|---|
| `producer` | Registra cada consulta, guarda originales y exclusiones, purga cada 24 horas y avisa de huecos al arrancar. Sigue montando `./data` en solo lectura |
| `catalog-loader` (perfil `tools`) | **Nuevo.** Imagen del productor; punto de entrada `python -m app.catalog_load`; monta `./data` con escritura; depende de `kafka` y `postgres` sanos; sin puertos; sin reinicio automático. Ver [catalog-loader.md](catalog-loader.md) |
| `usgs-stub` (solo en `compose.dev.yaml`, perfil `test`) | **Nuevo.** Fuente simulada para probar fallos; no forma parte de la entrega en ejecución |

`docker compose up --build -d` sigue arrancando exactamente cinco servicios.

## Variables de entorno

| Variable | Usada por | Por defecto | Significado |
|---|---|---|---|
| `USGS_FEED_URL` | productor | (ya existía) | Feed de 24 horas |
| `USGS_CATALOG_URL` | productor (aviso), carga | `https://earthquake.usgs.gov/fdsnws/event/1` | Base del catálogo histórico |
| `USGS_TIMEOUT_SECONDS` | productor, carga | `30` | Tiempo máximo por petición |
| `USGS_MAX_ATTEMPTS` | productor, carga | `4` | Peticiones por consulta, contando la primera |
| `USGS_USER_AGENT` | productor, carga | `seismic-observatory/1.0` | Identificación ante USGS; sin datos personales |
| `GAP_MARGIN_MINUTES` | productor, carga | `60` | Margen añadido a cada lado de un hueco |
| `PRODUCER_INTERVAL_SECONDS` | productor | `60` (ya existía) | Intervalo entre consultas |
| `RAW_PAYLOAD_RETENTION_DAYS` | productor | `7` (ya existía) | Retención de originales del feed; ahora se aplica |
| `DATA_DIR` | carga | `/data` | Raíz de los ficheros descargados dentro del contenedor |
| `LOADER_UID`, `LOADER_GID` | Compose | `0` | Usuario con el que escribe la carga en `./data`; en Linux, el propio |

`.env.example` las incluye todas con valores no secretos.

## Salud del productor

El latido se actualiza al terminar cada ciclo **registrado**, haya respondido bien la fuente o
no. Un fallo de USGS no vuelve `unhealthy` al productor: se ve en la antigüedad de
`last_ingestion`. El productor deja de estar sano si no puede registrar el ciclo (base o broker
no disponibles durante más de tres intervalos) o se bloquea.

## Fuente

- El productor no consulta el feed con más frecuencia que `PRODUCER_INTERVAL_SECONDS`.
- Si la fuente indica `Retry-After` mayor de 120 s, no se vuelve a consultar hasta que pase.
- Las peticiones llevan `If-Modified-Since` cuando se conoce el `Last-Modified` anterior.

## Datos

| Ruta en el equipo | En el contenedor | Contenido |
|---|---|---|
| `./data/usgs/catalog/` | `/data/usgs/catalog/` | Respuestas del catálogo sin modificar y resúmenes de carga. Fuera de Git |
