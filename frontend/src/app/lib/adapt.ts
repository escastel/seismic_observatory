// Pure adapters from the 006 API wire format (snake_case) to the panel types.
// They never throw: any unexpected shape becomes an `invalid_response` failure.

import type {
  ApiFailure,
  EventsMetadata,
  EventsPage,
  Health,
  MapEvent,
  Mode,
  Statistics,
} from './api-types';

export type AdaptResult<T> = { ok: true; value: T } | { ok: false; failure: ApiFailure };

class BadShape extends Error {}

type Obj = Record<string, unknown>;

function bad(what: string): never {
  throw new BadShape(what);
}

function isObj(v: unknown): v is Obj {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function obj(v: unknown, what: string): Obj {
  return isObj(v) ? v : bad(what);
}

function arr(v: unknown, what: string): unknown[] {
  return Array.isArray(v) ? v : bad(what);
}

/** Finite number or null; NaN/Infinity/other types become null (never 0). */
function numOrNull(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

function reqNum(v: unknown, what: string): number {
  const n = numOrNull(v);
  return n === null ? bad(what) : n;
}

function strOrNull(v: unknown): string | null {
  return typeof v === 'string' ? v : null;
}

function reqStr(v: unknown, what: string): string {
  return typeof v === 'string' ? v : bad(what);
}

function boolOrNull(v: unknown): boolean | null {
  return typeof v === 'boolean' ? v : null;
}

function reqBool(v: unknown, what: string): boolean {
  return typeof v === 'boolean' ? v : bad(what);
}

function mode(v: unknown, requested: Mode, what: string): Mode {
  if (v !== requested) bad(`${what}: modo distinto del pedido`);
  return requested;
}

function replayLabel(m: Obj, requested: Mode): string | null {
  if (requested !== 'replay') return null;
  const label = m['label'];
  if (typeof label !== 'string' || label.trim() === '') bad('metadata.label vacía en replay');
  return label;
}

function wrap<T>(fn: () => T): AdaptResult<T> {
  try {
    return { ok: true, value: fn() };
  } catch (e) {
    const detail = e instanceof BadShape ? e.message : 'forma inesperada';
    return {
      ok: false,
      failure: { kind: 'invalid_response', message: `Respuesta no válida: ${detail}` },
    };
  }
}

function adaptFeature(raw: unknown, requested: Mode): MapEvent {
  const f = obj(raw, 'feature');
  const id = typeof f['id'] === 'string' || typeof f['id'] === 'number' ? String(f['id']) : bad('feature.id');
  const p = obj(f['properties'], 'feature.properties');

  let lon: number | null = null;
  let lat: number | null = null;
  let depthKm: number | null = null;
  const g = f['geometry'];
  if (isObj(g) && g['type'] === 'Point' && Array.isArray(g['coordinates'])) {
    const c = g['coordinates'] as unknown[];
    lon = numOrNull(c[0]);
    lat = numOrNull(c[1]);
    depthKm = numOrNull(c[2]);
  }

  return {
    id,
    lon,
    lat,
    depthKm,
    mag: numOrNull(p['mag']),
    magType: strOrNull(p['magType']),
    place: strOrNull(p['place']),
    time: numOrNull(p['time']),
    updated: numOrNull(p['updated']),
    countryId: strOrNull(p['country_id']),
    countryName: strOrNull(p['country_name']),
    continent: strOrNull(p['continent']),
    subregion: strOrNull(p['subregion']),
    replayedAt: requested === 'replay' ? numOrNull(p['replayed_at']) : null,
    synthetic: requested === 'replay' ? boolOrNull(p['synthetic']) : null,
  };
}

export function adaptEvents(raw: unknown, requestedMode: Mode): AdaptResult<EventsPage> {
  return wrap(() => {
    const root = obj(raw, 'cuerpo');
    const m = obj(root['metadata'], 'metadata');
    mode(m['mode'], requestedMode, 'metadata.mode');
    const label = replayLabel(m, requestedMode);
    const period = obj(m['period'], 'metadata.period');
    const nm = obj(m['null_magnitude'], 'metadata.null_magnitude');
    const q = obj(m['quarantined'], 'metadata.quarantined');
    const features = arr(root['features'], 'features');

    const metadata: EventsMetadata = {
      generated: reqNum(m['generated'], 'metadata.generated'),
      lastIngestion: numOrNull(m['last_ingestion']),
      mode: requestedMode,
      count: reqNum(m['count'], 'metadata.count'),
      total: reqNum(m['total'], 'metadata.total'),
      truncated: reqBool(m['truncated'], 'metadata.truncated'),
      limit: reqNum(m['limit'], 'metadata.limit'),
      offset: reqNum(m['offset'], 'metadata.offset'),
      nextOffset: numOrNull(m['next_offset']),
      period: {
        start: numOrNull(period['start']),
        end: numOrNull(period['end']),
        defaultApplied: reqBool(period['default_applied'], 'period.default_applied'),
      },
      nullMagnitude: {
        count: reqNum(nm['count'], 'null_magnitude.count'),
        excluded: reqBool(nm['excluded'], 'null_magnitude.excluded'),
      },
      quarantined: {
        total: reqNum(q['total'], 'quarantined.total'),
        invalidGeometry: reqNum(q['invalid_geometry'], 'quarantined.invalid_geometry'),
      },
      label,
      lastReplayedAt: requestedMode === 'replay' ? numOrNull(m['last_replayed_at']) : null,
    };
    return { metadata, events: features.map((f) => adaptFeature(f, requestedMode)) };
  });
}

export function adaptStatistics(raw: unknown, requestedMode: Mode): AdaptResult<Statistics> {
  return wrap(() => {
    const r = obj(raw, 'cuerpo');
    mode(r['mode'], requestedMode, 'mode');
    const m = obj(r['metadata'], 'metadata');
    mode(m['mode'], requestedMode, 'metadata.mode');
    const label = replayLabel(m, requestedMode);
    const period = obj(r['period'], 'period');
    const f = obj(r['filters'], 'filters');
    const hourly = obj(r['hourly'], 'hourly');
    const byCountry = obj(r['by_country'], 'by_country');
    const mag = obj(r['magnitude_distribution'], 'magnitude_distribution');
    const depth = obj(r['depth_distribution'], 'depth_distribution');
    const cmp = obj(r['comparison'], 'comparison');
    const recent = obj(cmp['recent'], 'comparison.recent');
    const base = obj(cmp['baseline'], 'comparison.baseline');

    const ratioRaw = cmp['ratio'];
    const ratio: number | 'ND' = ratioRaw === 'ND' ? 'ND' : reqNum(ratioRaw, 'comparison.ratio');

    return {
      mode: requestedMode,
      generated: reqNum(m['generated'], 'metadata.generated'),
      lastIngestion: numOrNull(m['last_ingestion']),
      label,
      lastReplayedAt: requestedMode === 'replay' ? numOrNull(m['last_replayed_at']) : null,
      scope: reqStr(r['scope'], 'scope'),
      mapTruncated: reqBool(r['map_truncated'], 'map_truncated'),
      period: {
        start: reqNum(period['start'], 'period.start'),
        end: reqNum(period['end'], 'period.end'),
        defaultApplied: reqBool(period['default_applied'], 'period.default_applied'),
      },
      filters: {
        minMag: numOrNull(f['min_mag']),
        countryId: strOrNull(f['country_id']),
        excludeSynthetic: reqBool(f['exclude_synthetic'], 'filters.exclude_synthetic'),
      },
      unit: reqStr(r['unit'], 'unit'),
      total: reqNum(r['total'], 'total'),
      hourly: {
        window: reqStr(hourly['window'], 'hourly.window'),
        items: arr(hourly['items'], 'hourly.items').map((i) => {
          const o = obj(i, 'hourly.item');
          return { start: reqNum(o['start'], 'hourly.start'), count: reqNum(o['count'], 'hourly.count') };
        }),
      },
      byCountry: {
        items: arr(byCountry['items'], 'by_country.items').map((i) => {
          const o = obj(i, 'by_country.item');
          return {
            countryId: strOrNull(o['country_id']),
            countryName: strOrNull(o['country_name']) ?? 'Sin país asignado',
            count: reqNum(o['count'], 'by_country.count'),
          };
        }),
      },
      magnitudeDistribution: {
        unit: reqStr(mag['unit'], 'magnitude_distribution.unit'),
        items: arr(mag['items'], 'magnitude_distribution.items').map((i) => {
          const o = obj(i, 'magnitude.item');
          return {
            from: reqNum(o['from'], 'magnitude.from'),
            to: reqNum(o['to'], 'magnitude.to'),
            count: reqNum(o['count'], 'magnitude.count'),
          };
        }),
        unvalued: reqNum(mag['unvalued'], 'magnitude_distribution.unvalued'),
      },
      depthDistribution: {
        unit: reqStr(depth['unit'], 'depth_distribution.unit'),
        items: arr(depth['items'], 'depth_distribution.items').map((i) => {
          const o = obj(i, 'depth.item');
          return {
            label: reqStr(o['label'], 'depth.label'),
            from: numOrNull(o['from']),
            to: numOrNull(o['to']),
            count: reqNum(o['count'], 'depth.count'),
          };
        }),
        unvalued: reqNum(depth['unvalued'], 'depth_distribution.unvalued'),
      },
      comparison: {
        recent: {
          start: reqNum(recent['start'], 'recent.start'),
          end: reqNum(recent['end'], 'recent.end'),
          count: reqNum(recent['count'], 'recent.count'),
        },
        baseline: {
          year: reqNum(base['year'], 'baseline.year'),
          events: reqNum(base['events'], 'baseline.events'),
          days: reqNum(base['days'], 'baseline.days'),
          dailyMean: reqNum(base['daily_mean'], 'baseline.daily_mean'),
        },
        ratio,
        filtersApplied: arr(cmp['filters_applied'], 'comparison.filters_applied').map((s) =>
          reqStr(s, 'filters_applied'),
        ),
        warning: reqStr(cmp['warning'], 'comparison.warning'),
      },
    };
  });
}

export function adaptHealth(raw: unknown): AdaptResult<Health> {
  return wrap(() => {
    const r = obj(raw, 'cuerpo');
    const status = r['status'];
    if (status !== 'ok' && status !== 'degraded') bad('status');
    return {
      status,
      database: reqStr(r['database'], 'database'),
      replayDatabase: reqStr(r['replay_database'], 'replay_database'),
      generated: reqNum(r['generated'], 'generated'),
      lastIngestion: numOrNull(r['last_ingestion']),
    };
  });
}

export function parseFailure(status: number, body: unknown): ApiFailure {
  if (status === 422) {
    let param: string | undefined;
    let message = 'Filtro no válido';
    if (isObj(body) && Array.isArray(body['detail']) && isObj(body['detail'][0])) {
      const d = body['detail'][0] as Obj;
      if (typeof d['param'] === 'string') param = d['param'];
      if (typeof d['message'] === 'string' && d['message'] !== '') message = d['message'];
    }
    return param === undefined
      ? { kind: 'invalid_parameters', message }
      : { kind: 'invalid_parameters', message, param };
  }
  if (status === 503) {
    return { kind: 'database_unavailable', message: 'La base de datos no está disponible' };
  }
  if (status === 500) {
    return { kind: 'server_error', message: 'Error interno del servidor' };
  }
  return { kind: 'unreachable', message: 'No se puede contactar con el backend' };
}
