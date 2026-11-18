import { describe, expect, it } from 'vitest';
import type { PanelStatus, Reading, Statistics } from './api-types';
import { buildStatusBar } from './status-bar';

const T0 = Date.UTC(2026, 10, 1, 0, 0, 0);

function stats(over: Partial<Statistics> = {}): Statistics {
  return {
    mode: 'live',
    generated: T0,
    lastIngestion: T0 - 60_000,
    label: null,
    lastReplayedAt: null,
    scope: 'all',
    mapTruncated: false,
    period: { start: T0, end: T0 + 86_400_000, defaultApplied: true },
    filters: { minMag: null, countryId: null, excludeSynthetic: false },
    unit: 'eventos',
    total: 1234,
    hourly: { window: '168h', items: [] },
    byCountry: { items: [] },
    magnitudeDistribution: { unit: 'M', items: [], unvalued: 7 },
    depthDistribution: { unit: 'km', items: [], unvalued: 0 },
    comparison: {
      recent: { start: 0, end: 0, count: 0 },
      baseline: { year: 2025, events: 0, days: 0, dailyMean: 0 },
      ratio: 'ND',
      filtersApplied: [],
      warning: ''
    },
    ...over
  };
}

const okStatus: PanelStatus = {
  keys: ['ok'],
  messages: ['Datos al día.'],
  ingestionAgeMs: 60_000,
  showingPreviousReading: false
};

function reading(mode: 'live' | 'replay' = 'live', events = 2): Reading {
  return {
    readAt: T0 + 5_000,
    filters: { mode, start: null, end: null, minMag: null, countryId: null, excludeSynthetic: false },
    events: Array.from({ length: events }, (_, i) => ({ id: String(i) }) as Reading['events'][number]),
    metadata: {
      generated: T0 + 1_000,
      lastIngestion: T0 - 60_000,
      mode,
      count: events,
      total: 1234,
      truncated: false,
      limit: 100,
      offset: 0,
      nextOffset: null,
      period: { start: T0, end: T0 + 86_400_000, defaultApplied: true },
      nullMagnitude: { count: 4, excluded: false },
      quarantined: { total: 9, invalidGeometry: 3 },
      label: null,
      lastReplayedAt: T0 - 120_000
    },
    statistics: null,
    health: null
  };
}

const detail = (bar: ReturnType<typeof buildStatusBar>, id: string) => bar.details.find((d) => d.id === id);

describe('buildStatusBar metrics', () => {
  it('returns the five metrics, three of them visible on narrow screens', () => {
    const bar = buildStatusBar(stats(), okStatus, reading());
    expect(bar.metrics.map((m) => m.id)).toEqual(['total', 'lastIngestion', 'status', 'period', 'unvalued']);
    expect(bar.metrics.filter((m) => m.visibleOnNarrow).map((m) => m.id)).toEqual(['total', 'lastIngestion', 'status']);
  });

  it('takes the total from the statistics, not from the events of the map', () => {
    const bar = buildStatusBar(stats({ total: 1234 }), okStatus, reading('live', 2));
    expect(bar.metrics[0].value).toBe('1234');
  });

  it('shows ND for every figure when there is no data', () => {
    const bar = buildStatusBar(null, null, null);
    for (const id of ['total', 'lastIngestion', 'status', 'period', 'unvalued']) {
      expect(bar.metrics.find((m) => m.id === id)?.value).toBe('ND');
    }
    for (const d of bar.details) expect(d.value).toBe('ND');
  });

  it('labels replay mode on every metric', () => {
    const bar = buildStatusBar(stats({ mode: 'replay' }), okStatus, reading('replay'));
    for (const m of bar.metrics) expect(m.badge).toBe('REPRODUCCIÓN');
  });

  it('labels replay mode even without statistics', () => {
    const bar = buildStatusBar(null, okStatus, reading('replay'));
    for (const m of bar.metrics) expect(m.badge).toBe('REPRODUCCIÓN');
  });

  it('has no badge in live mode', () => {
    const bar = buildStatusBar(stats(), okStatus, reading());
    for (const m of bar.metrics) expect(m.badge).toBeNull();
  });
});

describe('buildStatusBar details', () => {
  it('reports the last read, the response generation and the last ingestion', () => {
    const bar = buildStatusBar(stats(), okStatus, reading());
    expect(detail(bar, 'lastRead')?.value).toBe('2026-11-01 00:00:05 UTC');
    expect(detail(bar, 'generated')?.value).toBe('2026-11-01 00:00:01 UTC');
    expect(detail(bar, 'lastIngestion')?.value).toBe('2026-10-31 23:59:00 UTC');
  });

  it('shows the last replay only in replay mode', () => {
    expect(detail(buildStatusBar(stats(), okStatus, reading('live')), 'lastReplay')).toBeUndefined();
    const replay = buildStatusBar(stats({ mode: 'replay' }), okStatus, reading('replay'));
    expect(detail(replay, 'lastReplay')?.value).toBe('2026-10-31 23:58:00 UTC');
  });

  it('reports quarantine with the invalid geometry count', () => {
    const v = detail(buildStatusBar(stats(), okStatus, reading()), 'quarantine')?.value ?? '';
    expect(v).toContain('9');
    expect(v).toContain('3');
  });

  it('reports events without magnitude as included or excluded', () => {
    const included = detail(buildStatusBar(stats(), okStatus, reading()), 'unvalued')?.value ?? '';
    expect(included).toContain('4');
    const r = reading();
    r.metadata.nullMagnitude = { count: 4, excluded: true };
    const excluded = detail(buildStatusBar(stats(), okStatus, r), 'unvalued')?.value ?? '';
    expect(excluded).toContain('4');
    expect(excluded).not.toBe(included);
  });
});

describe('compact bar values (the full text moves to detail and «Detalles»)', () => {
  const metric = (bar: ReturnType<typeof buildStatusBar>, id: string) => bar.metrics.find((m) => m.id === id)!;

  it('shows the default period as «Últimas 24 h» and keeps the range in the detail', () => {
    const m = metric(buildStatusBar(stats(), okStatus, reading()), 'period');
    expect(m.value).toBe('Últimas 24 h');
    expect(m.detail).toContain('2026-11-01 00:00:00 UTC');
  });

  it('shows an explicit period as a short range', () => {
    const custom = stats({ period: { start: T0, end: T0 + 3_600_000, defaultApplied: false } });
    expect(metric(buildStatusBar(custom, okStatus, reading()), 'period').value).toBe('11-01 00:00 → 11-01 01:00');
  });

  it('shows only the time of the last ingestion and keeps the date in the detail', () => {
    const m = metric(buildStatusBar(stats(), okStatus, reading()), 'lastIngestion');
    expect(m.value).toBe('23:59:00');
    expect(m.detail).toContain('2026-10-31');
  });

  it('shows the two unvalued counts as «a · b»', () => {
    expect(metric(buildStatusBar(stats(), okStatus, reading()), 'unvalued').value).toBe('7 · 0');
  });

  it('keeps ND untouched without statistics', () => {
    const bar = buildStatusBar(null, null, null);
    expect(metric(bar, 'period').value).toBe('ND');
  });
});
