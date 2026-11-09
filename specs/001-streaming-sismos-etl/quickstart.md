# Quickstart de validación

## Prerrequisitos

- Docker Engine y Docker Compose disponibles.
- Acceso local al repositorio.
- `paises.geojson` de Natural Earth y un histórico JSONL de 2025 para replay.
- No se requieren servicios Cloud; Netlify/ngrok solo son necesarios para probar
  el frontend remoto.

## Arranque

Desde la raíz del repositorio:

```powershell
docker compose up --build -d
docker compose ps
```

Esperar a que Kafka y PostgreSQL estén saludables y que API, Productor y Consumidor
estén activos. Este es el único comando de arranque backend admitido.

## Validar ingesta y WAF

1. Confirmar que el Productor ejecuta el ciclo de 60 segundos y publica en
   `terremotos_raw`.
2. Publicar un evento válido y verificar una fila en `fact_sismos`.
3. Publicar un evento con `mag: null` y otro con latitud `91`; verificar dos filas en
   `cuarentena`, con dimensiones Completitud y Validez respectivamente.
4. Publicar un punto marítimo; verificar `country = 'Sin país asignado'`.
5. Publicar el mismo `id` dos veces: primero con `updated` antiguo y después con
   `updated` nuevo. Verificar una sola fila y que prevalece la fecha nueva.
6. Detener temporalmente PostgreSQL, procesar un evento y verificar que el offset
   no se confirma; al recuperar PostgreSQL el evento se reintenta.

## Validar API

```powershell
curl "http://localhost:8000/api/eventos?format=geojson&min_magnitude=4"
curl "http://localhost:8000/api/estadisticas/paises"
curl "http://localhost:8000/api/estadisticas/timeline?bucket=month"
```

Comprobar que el primer resultado es `FeatureCollection`, que los filtros se
combinan y que las estadísticas coinciden con el dataset cargado. Probar también
un rango de fechas invertido y esperar HTTP 400.

## Validar CORS y frontend

Configurar `frontend/public/config.json` con la URL del API/ngrok, publicar el
frontend según `netlify.toml` y comprobar una petición desde el origen Netlify.
La respuesta debe incluir CORS permitido y el mapa debe mostrar eventos sin error
de navegador.

## Validar replay de 2025

1. Publicar el JSONL histórico en `terremotos_replay` usando la herramienta de
   replay con una tasa al menos 10 veces superior a un evento por 60 segundos.
2. Registrar el número de mensajes publicados, persistidos y puestos en cuarentena.
3. Consultar la API y verificar que los conteos son trazables al lote y que una
   segunda ejecución no crea duplicados.
4. Documentar manualmente resultados y decisiones de calidad; no generar un informe
   automático.

## Limpieza

Para detener servicios sin borrar el volumen de datos:

```powershell
docker compose down
```

No usar `docker compose down -v` durante una validación de idempotencia o replay,
porque elimina la evidencia persistida.
