import { describe, expect, it } from 'vitest';
import { adaptEvents, adaptHealth, adaptStatistics, parseFailure } from './adapt';

function eventsBody(over: Record<string, unknown> = {}, meta: Record<string, unknown> = {}, features?: unknown[]) {
  return {
    type: 'FeatureCollection',
    metadata: {
      generated: 1793113200000,
      last_ingestion: 1793113140000,
      mode: 'live',
      count: 1,
      total: 1,
      truncated: false,
      limit: 1000,
      offset: 0,
      next_offset: null,
      period: { start: 1793026800000, end: null, default_applied: true },
      null_magnitude: { count: 0, excluded: false },
      quarantined: { total: 0, invalid_geometry: 0 },
      ...meta,
    },
    features: features ?? [
      {
        type: 'Feature',
        id: 'ejemplo',
        geometry: { type: 'Point', coordinates: [-3.7, 40.4, 12.0] },
        properties: {
          mag: 3.2, magType: 'ml', place: 'Ejemplo', time: 1793109600000, updated: 1793110000000,
          country_id: 'ESP', country_name: 'España', continent: 'Europe', subregion: 'Southern Europe',
        },
      },
    ],
    ...over,
  };
}

describe('adaptEvents', () => {
  it('adapts a live response', () => {
    const r = adaptEvents(eventsBody(), 'live');
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.value.metadata.label).toBeNull();
    expect(r.value.metadata.period.defaultApplied).toBe(true);
    expect(r.value.metadata.nextOffset).toBeNull();
    expect(r.value.events[0]).toMatchObject({
      id: 'ejemplo', lon: -3.7, lat: 40.4, depthKm: 12, mag: 3.2, countryId: 'ESP', countryName: 'España',
      replayedAt: null, synthetic: null,
    });
  });

  it('keeps null magnitude as null and a sea event with null country', () => {
    const f = {
      type: 'Feature', id: 'mar',
      geometry: { type: 'Point', coordinates: [10, 20, null] },
      properties: { mag: null, magType: null, place: null, time: 1, updated: 2, country_id: null, country_name: null,
        continent: null, subregion: null },
    };
    const r = adaptEvents(eventsBody({}, {}, [f]), 'live');
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.value.events[0].mag).toBeNull();
    expect(r.value.events[0].depthKm).toBeNull();
    expect(r.value.events[0].countryId).toBeNull();
    expect(r.value.events[0].countryName).toBeNull();
  });

  it('turns NaN and Infinity into null', () => {
    const f = {
      type: 'Feature', id: 'x',
      geometry: { type: 'Point', coordinates: [Infinity, NaN, 5] },
      properties: { mag: NaN, time: Infinity },
    };
    const r = adaptEvents(eventsBody({}, {}, [f]), 'live');
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.value.events[0]).toMatchObject({ lon: null, lat: null, depthKm: 5, mag: null, time: null });
  });

  it('keeps features without geometry with null coordinates', () => {
    const f = { type: 'Feature', id: 'g', geometry: null, properties: { mag: 2 } };
    const r = adaptEvents(eventsBody({}, {}, [f]), 'live');
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.value.events[0]).toMatchObject({ lon: null, lat: null, depthKm: null, mag: 2 });
  });

  it('adapts a replay response with label', () => {
    const body = eventsBody({}, { mode: 'replay', label: 'REPRODUCCIÓN', last_replayed_at: 5 }, [
      {
        type: 'Feature', id: 'r', geometry: { type: 'Point', coordinates: [1, 2, 3] },
        properties: { mag: 4, replayed_at: 99, synthetic: true, country_id: 'FRA', country_name: 'Francia' },
      },
    ]);
    const r = adaptEvents(body, 'replay');
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.value.metadata.label).toBe('REPRODUCCIÓN');
    expect(r.value.metadata.lastReplayedAt).toBe(5);
    expect(r.value.events[0]).toMatchObject({ replayedAt: 99, synthetic: true });
  });

  it('rejects a wrong mode', () => {
    const r = adaptEvents(eventsBody(), 'replay');
    expect(r).toMatchObject({ ok: false, failure: { kind: 'invalid_response' } });
    const r2 = adaptEvents(eventsBody({}, { mode: 'replay', label: 'REPRODUCCIÓN' }), 'live');
    expect(r2).toMatchObject({ ok: false, failure: { kind: 'invalid_response' } });
  });

  it('rejects replay without label or with an empty one', () => {
    expect(adaptEvents(eventsBody({}, { mode: 'replay' }), 'replay').ok).toBe(false);
    expect(adaptEvents(eventsBody({}, { mode: 'replay', label: '  ' }), 'replay').ok).toBe(false);
  });

  it.each([null, undefined, 42, 'texto', [], {}, { metadata: {}, features: [] }, { metadata: null }])(
    'does not throw on garbage %#',
    (g) => {
      const r = adaptEvents(g, 'live');
      expect(r).toMatchObject({ ok: false, failure: { kind: 'invalid_response' } });
    },
  );

  it('rejects features that are not an array', () => {
    expect(adaptEvents(eventsBody({ features: 'x' }), 'live').ok).toBe(false);
  });
});

function statsBody(over: Record<string, unknown> = {}, meta: Record<string, unknown> = {}) {
  return {
    mode: 'live',
    metadata: { generated: 10, last_ingestion: 9, mode: 'live', ...meta },
    scope: 'complete',
    map_truncated: false,
    period: { start: 0, end: 7200000, default_applied: true },
    filters: { min_mag: null, country_id: null, exclude_synthetic: false },
    unit: 'events',
    total: 3,
    hourly: { window: '1 hour UTC, end excluded', items: [{ start: 0, count: 1 }, { start: 3600000, count: 2 }] },
    by_country: { items: [{ country_id: 'ESP', country_name: 'España', count: 2 }, { country_id: null, country_name: 'Sin país asignado', count: 1 }] },
    magnitude_distribution: { unit: 'magnitude (floor, 1 unit bins)', items: [{ from: 4, to: 5, count: 2 }], unvalued: 1 },
    depth_distribution: { unit: 'km', items: [{ label: '0-70', from: 0, to: 70, count: 2 }, { label: '300+', from: 300, to: null, count: 0 }], unvalued: 1 },
    comparison: {
      recent: { start: 0, end: 7200000, count: 3 },
      baseline: { year: 2025, events: 0, days: 365, daily_mean: 0.0 },
      ratio: 'ND',
      filters_applied: ['min_mag'],
      warning: 'El periodo reciente puede estar incompleto.',
    },
    ...over,
  };
}

describe('adaptStatistics', () => {
  it('adapts a live response with ratio ND', () => {
    const r = adaptStatistics(statsBody(), 'live');
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.value.comparison.ratio).toBe('ND');
    expect(r.value.byCountry.items[1]).toMatchObject({ countryId: null, countryName: 'Sin país asignado' });
    expect(r.value.depthDistribution.items[1].to).toBeNull();
    expect(r.value.hourly.items).toHaveLength(2);
    expect(r.value.lastIngestion).toBe(9);
    expect(r.value.label).toBeNull();
  });

  it('accepts open-ended depth bins as the real API sends them (from null for "<0")', () => {
    const body = statsBody() as Record<string, any>;
    body['depth_distribution'] = {
      unit: 'km',
      items: [{ label: '<0', from: null, to: 0, count: 1 }, { label: '>=300', from: 300, to: null, count: 1 }],
      unvalued: 0
    };
    const r = adaptStatistics(body, 'live');
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.value.depthDistribution.items[0]).toMatchObject({ from: null, to: 0, count: 1 });
  });

  it('keeps a numeric ratio', () => {
    const b = statsBody();
    (b.comparison as { ratio: unknown }).ratio = 1.5;
    const r = adaptStatistics(b, 'live');
    expect(r.ok && r.value.comparison.ratio).toBe(1.5);
  });

  it('adapts replay with label', () => {
    const b = statsBody({ mode: 'replay' }, { mode: 'replay', label: 'REPRODUCCIÓN', last_replayed_at: 7 });
    const r = adaptStatistics(b, 'replay');
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.value).toMatchObject({ label: 'REPRODUCCIÓN', lastReplayedAt: 7 });
  });

  it('rejects wrong mode, missing label and garbage', () => {
    expect(adaptStatistics(statsBody(), 'replay').ok).toBe(false);
    expect(adaptStatistics(statsBody({ mode: 'replay' }, { mode: 'replay' }), 'replay').ok).toBe(false);
    expect(adaptStatistics(statsBody({ countries: [] , by_country: undefined }), 'live').ok).toBe(false);
    expect(adaptStatistics('basura', 'live')).toMatchObject({ ok: false, failure: { kind: 'invalid_response' } });
  });

  it('rejects an invalid ratio string', () => {
    const b = statsBody();
    (b.comparison as { ratio: unknown }).ratio = 'abc';
    expect(adaptStatistics(b, 'live').ok).toBe(false);
  });
});

describe('adaptHealth', () => {
  it('adapts ok and degraded', () => {
    const ok = adaptHealth({ status: 'ok', database: 'ok', replay_database: 'ok', generated: 1, last_ingestion: 0 });
    expect(ok).toMatchObject({ ok: true, value: { status: 'ok', replayDatabase: 'ok', lastIngestion: 0 } });
    const deg = adaptHealth({ status: 'degraded', database: 'unavailable', replay_database: 'ok', generated: 1, last_ingestion: null });
    expect(deg).toMatchObject({ ok: true, value: { status: 'degraded', lastIngestion: null } });
  });

  it('rejects garbage', () => {
    expect(adaptHealth(null).ok).toBe(false);
    expect(adaptHealth({ status: 'fine' }).ok).toBe(false);
  });
});

describe('parseFailure', () => {
  it('maps 422 with param and message', () => {
    const f = parseFailure(422, { error: 'invalid_parameters', detail: [{ param: 'start', message: 'sin zona' }] });
    expect(f).toEqual({ kind: 'invalid_parameters', message: 'sin zona', param: 'start' });
  });

  it('maps 422 with malformed body', () => {
    expect(parseFailure(422, 'x').kind).toBe('invalid_parameters');
    expect(parseFailure(422, null).param).toBeUndefined();
  });

  it('maps other statuses', () => {
    expect(parseFailure(503, { error: 'database_unavailable' }).kind).toBe('database_unavailable');
    expect(parseFailure(500, null).kind).toBe('server_error');
    expect(parseFailure(404, null).kind).toBe('unreachable');
    expect(parseFailure(0, undefined).kind).toBe('unreachable');
  });
});
