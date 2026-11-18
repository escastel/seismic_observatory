"""Texts of the public OpenAPI documentation (Spanish). Constants only: no FastAPI import.

The data contract is the one of specs/006-query-api/contracts/api.md; nothing here changes it.
"""

from __future__ import annotations

from typing import Any

API_TITLE = "Observatorio Sísmico · API"

API_DESCRIPTION = """\
API de **solo lectura** del Observatorio Sísmico: eventos sísmicos de USGS procesados por este
proyecto y sus estadísticas agregadas.

**Procedencia y límites.** Los datos proceden de USGS y los trata el proyecto de forma
descriptiva. **No es una predicción ni una evaluación de riesgo**: no sirve para decidir nada
sobre la seguridad de personas o bienes.

**Uso.**

- Solo se admiten peticiones `GET` (y `OPTIONS` para CORS); no hay ninguna ruta de escritura.
- Límite de **60 peticiones por minuto por visitante**. Al superarlo se responde `429` con la
  cabecera `Retry-After: 60`.
- La primera visita desde un navegador a un dominio gratuito de ngrok muestra una página
  intermedia. El botón «Probar» ya envía la cabecera `ngrok-skip-browser-warning: true` que la
  evita.
- Los tiempos son milisegundos Unix en UTC.

**Privacidad.** Para cargar esta página el navegador se conecta a `cdn.jsdelivr.net`, que ve su
dirección IP y el `Referer`.
"""

TAGS: list[dict[str, str]] = [
    {"name": "eventos", "description": "Eventos sísmicos individuales, paginados, en formato GeoJSON."},
    {"name": "estadisticas", "description": "Agregaciones sobre todo el conjunto filtrado."},
    {"name": "salud", "description": "Estado del servicio y de sus bases de datos."},
]

# --- operations -----------------------------------------------------------------------------

EVENTS_SUMMARY = "Listar eventos sísmicos"
EVENTS_DESCRIPTION = """\
Devuelve una `FeatureCollection` GeoJSON con los eventos que cumplen los filtros y un bloque
`metadata` (total, página, periodo aplicado, eventos sin magnitud y cuarentena).

Sin `start`, en modo `live` se usan las últimas 24 horas. `start` es inclusivo y `end`
exclusivo. Para paginar, repite la petición con el `next_offset` de `metadata` mientras
`truncated` sea `true`.
"""

STATISTICS_SUMMARY = "Obtener estadísticas agregadas"
STATISTICS_DESCRIPTION = """\
Agregaciones sobre **todo** el conjunto filtrado (nunca sobre una página): recuento total,
eventos por hora, por país, distribución de magnitudes y de profundidades, y comparación con un
año de referencia.

Aplica los mismos filtros que `/api/eventos`. Un periodo que genere más de 10.000 ventanas
horarias se rechaza con 422.
"""

HEALTH_SUMMARY = "Comprobar el estado del servicio"
HEALTH_DESCRIPTION = """\
Responde siempre 200. `status` es `ok` si responden las bases de datos en vivo y de
reproducción, y `degraded` si alguna no puede responder. No expone credenciales.
"""

# --- parameters (description, example) ---------------------------------------------------------

MODE_DESCRIPTION = "Origen de los datos: `live` (datos reales) o `replay` (reproducción). Otro valor da 422."
MODE_EXAMPLE = "live"

START_DESCRIPTION = (
    "Inicio del periodo (inclusivo), ISO 8601 con zona horaria; sin zona da 422. "
    "Por defecto, solo en `live`: 24 horas antes de `end` (o de ahora si tampoco hay `end`)."
)
START_EXAMPLE = "2026-11-17T00:00:00Z"

END_DESCRIPTION = (
    "Fin del periodo (exclusivo), ISO 8601 con zona horaria. Sin cota por defecto. "
    "Si `start` es mayor o igual que `end`, da 422."
)
END_EXAMPLE = "2026-11-18T00:00:00Z"

MIN_MAG_DESCRIPTION = "Magnitud mínima (número finito). Sin filtro por defecto; los eventos sin magnitud no la cumplen."
MIN_MAG_EXAMPLE = 5.0

COUNTRY_ID_DESCRIPTION = "Identificador de país: de 1 a 8 caracteres alfanuméricos. Sin filtro por defecto."
COUNTRY_ID_EXAMPLE = "JP"

EXCLUDE_SYNTHETIC_DESCRIPTION = "Excluye los eventos sintéticos. Solo tiene efecto en `replay`. Por defecto `false`."
EXCLUDE_SYNTHETIC_EXAMPLE = False

LIMIT_DESCRIPTION = (
    "Tamaño de página: de 1 al máximo configurado (por defecto, ese máximo, 1000). Fuera de rango da 422."
)
LIMIT_EXAMPLE = 100

OFFSET_DESCRIPTION = "Eventos que se saltan desde el principio (mayor o igual que 0). Por defecto 0."
OFFSET_EXAMPLE = 0

BASELINE_YEAR_DESCRIPTION = "Año de referencia de la comparación (de 1900 a 2100). Por defecto 2025."
BASELINE_YEAR_EXAMPLE = 2025

# --- error response examples (exact shapes produced by api/app/main.py) --------------------------

ERROR_422_DESCRIPTION = "Parámetro inválido."
ERROR_422_EXAMPLE: dict[str, Any] = {
    "error": "invalid_parameters",
    "detail": [{"param": "min_mag", "message": "must be a finite number"}],
}

ERROR_503_DESCRIPTION = "Base de datos no disponible (pool sin abrir, caída o tiempo agotado)."
ERROR_503_EXAMPLE: dict[str, Any] = {
    "error": "database_unavailable",
    "detail": "The live database is not available",
}

ERROR_500_DESCRIPTION = "Error inesperado; el detalle está en el registro de la API."
ERROR_500_EXAMPLE: dict[str, Any] = {
    "error": "internal_error",
    "detail": "Unexpected error; see the API log",
}

# --- 200 examples ------------------------------------------------------------------------------

EVENTS_200_DESCRIPTION = "FeatureCollection GeoJSON con el bloque `metadata`."
EVENTS_200_EXAMPLE: dict[str, Any] = {
    "type": "FeatureCollection",
    "metadata": {
        "generated": 1793113200000,
        "last_ingestion": 1793113140000,
        "mode": "live",
        "count": 0,
        "total": 0,
        "truncated": False,
        "limit": 1000,
        "offset": 0,
        "next_offset": None,
        "period": {"start": 1793026800000, "end": None, "default_applied": True},
        "null_magnitude": {"count": 0, "excluded": False},
        "quarantined": {"total": 0, "invalid_geometry": 0},
    },
    "features": [],
}

STATISTICS_200_DESCRIPTION = "Agregaciones sobre todo el conjunto filtrado."

HEALTH_200_DESCRIPTION = "Estado del servicio: `ok` o `degraded`."
HEALTH_200_EXAMPLE: dict[str, Any] = {
    "status": "ok",
    "database": "ok",
    "replay_database": "ok",
    "generated": 1793113200000,
    "last_ingestion": 1793113140000,
}
