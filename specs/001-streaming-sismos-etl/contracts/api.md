# API Contract

Base path: `/api`. JSON is the default media type. Clients may request
`application/geo+json` or set `format=geojson` for `/eventos`.

## CORS

FastAPI MUST install CORS middleware. `CORS_ORIGINS` is a comma-separated
configuration value; the demo default is `*`, while Netlify/ngrok deployments
should provide explicit origins. Allowed methods are `GET, OPTIONS`, allowed
headers include `Content-Type` and `ngrok-skip-browser-warning`, and credentials
remain disabled when wildcard origins are used.

## `GET /eventos`

Query parameters:

| Parameter | Type | Meaning |
|---|---|---|
| `country` | string | exact country, including `Sin país asignado` |
| `date_from` | ISO date/time | inclusive lower bound |
| `date_to` | ISO date/time | inclusive upper bound (legacy compatibility) |
| `start` | ISO8601 | inclusive lower bound |
| `end` | ISO8601 | exclusive upper bound |
| `min_mag` | number | inclusive lower bound |
| `country_id` | string | Natural Earth `ADM0_A3` |
| `min_magnitude` | number | inclusive lower bound |
| `max_magnitude` | number | inclusive upper bound |
| `format` | `json`/`geojson` | response shape; default `json` |
| `limit` | integer | 1-10000; default 1000 |
| `offset` | integer | non-negative; default 0 |

Without an explicit `start`/`date_from`, `/eventos` defaults to the previous
24 hours. Statistics use the same explicitly supplied filters.

JSON response:

```json
{
  "items": [
    {
      "id": "us7000example",
      "updated": "2025-01-02T03:04:05Z",
      "time": "2025-01-02T03:00:00Z",
      "mag": 4.2,
      "place": "Example",
      "longitude": -70.1,
      "latitude": 10.2,
      "depth_km": 12.0,
      "magType": "ml",
      "country": "Chile",
      "country_name": "Chile",
      "country_id": "CHL",
      "continent": "South America",
      "subregion": "South America",
      "source_topic": "terremotos_raw"
    }
  ],
  "count": 1,
  "limit": 1000,
  "offset": 0
}
```

GeoJSON response MUST be a `FeatureCollection` of `Point` features with
`[longitude, latitude, depth_km]` coordinates when depth exists and the event
attributes in `properties`.

## `GET /estadisticas/paises`

Returns:

```json
{
  "items": [
    {"country": "Chile", "count": 12},
    {"country": "Sin país asignado", "count": 8}
  ]
}
```

Accepts the same date and magnitude filters as `/eventos`.

## `GET /estadisticas/timeline`

Query parameter `bucket` accepts `day`, `week` or `month` (default `day`) and
returns:

```json
{
  "bucket": "month",
  "items": [
    {"period": "2025-01", "count": 20}
  ]
}
```

Accepts date and magnitude filters. `bucket` outside the allowed set returns HTTP
400.

## Errors

Invalid filters return HTTP 400 with:

```json
{"detail": "date_from must be earlier than or equal to date_to"}
```

Database unavailability returns HTTP 503 with a non-sensitive message. Empty
results are successful responses with `items: []` or an empty GeoJSON
`FeatureCollection`.
