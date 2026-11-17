import { describe, expect, it } from 'vitest';
import type { PanelStatus, Statistics } from './api-types';
import { buildSummaryCards } from './summary';

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

const byId = (cards: ReturnType<typeof buildSummaryCards>, id: string) => cards.find((c) => c.id === id)!;

describe('buildSummaryCards', () => {
  it('returns exactly the five cards, without a maximum magnitude card', () => {
    const cards = buildSummaryCards(stats(), okStatus);
    expect(cards.map((c) => c.id)).toEqual(['total', 'lastIngestion', 'status', 'period', 'unvalued']);
    expect(cards.some((c) => /máxima/i.test(c.label))).toBe(false);
  });

  it('takes the total from Statistics and shows 0 as 0', () => {
    expect(byId(buildSummaryCards(stats(), okStatus), 'total').value).toBe('1234');
    expect(byId(buildSummaryCards(stats({ total: 0 }), okStatus), 'total').value).toBe('0');
  });

  it('shows the last ingestion in UTC', () => {
    const c = byId(buildSummaryCards(stats(), okStatus), 'lastIngestion');
    expect(c.value).toBe('2026-10-31 23:59:00 UTC');
    expect(c.unit).toBe('UTC');
  });

  it('shows the status as text with a tone, not only colour', () => {
    const stale: PanelStatus = { keys: ['stale'], messages: ['Datos desactualizados'], ingestionAgeMs: 1, showingPreviousReading: false };
    const down: PanelStatus = { keys: ['unreachable'], messages: ['x'], ingestionAgeMs: null, showingPreviousReading: false };
    expect(byId(buildSummaryCards(stats(), okStatus), 'status')).toMatchObject({ value: 'Al día', tone: 'ok' });
    expect(byId(buildSummaryCards(stats(), stale), 'status')).toMatchObject({ value: 'Desactualizado', tone: 'warning' });
    expect(byId(buildSummaryCards(stats(), down), 'status')).toMatchObject({ value: 'Backend inaccesible', tone: 'error' });
  });

  it('reports the period and the unvalued counts separately', () => {
    const cards = buildSummaryCards(stats({ depthDistribution: { unit: 'km', items: [], unvalued: 3 } }), okStatus);
    expect(byId(cards, 'period').value).toContain('2026-11-01 00:00:00 UTC');
    const unvalued = byId(cards, 'unvalued');
    expect(unvalued.detail).toContain('Sin magnitud: 7');
    expect(unvalued.detail).toContain('Sin profundidad: 3');
  });

  it('shows ND when there is no data', () => {
    const cards = buildSummaryCards(null, null);
    for (const c of cards) expect(c.value).toBe('ND');
    expect(cards.every((c) => c.badge === null)).toBe(true);
  });

  it('describes the applied filters', () => {
    const s = stats({ filters: { minMag: 4.5, countryId: 'CL', excludeSynthetic: true } });
    const detail = byId(buildSummaryCards(s, okStatus), 'total').detail;
    expect(detail).toContain('magnitud mínima 4,5');
    expect(detail).toContain('CL');
    expect(detail).toContain('sin sintéticos');
    expect(byId(buildSummaryCards(stats(), okStatus), 'total').detail).toBe('Sin filtros');
  });

  it('labels every card REPRODUCCIÓN in replay mode', () => {
    const cards = buildSummaryCards(stats({ mode: 'replay', label: 'REPRODUCCIÓN' }), okStatus);
    expect(cards.every((c) => c.badge === 'REPRODUCCIÓN')).toBe(true);
  });
});
