import { describe, expect, it } from 'vitest';
import {
  barWidthPercent,
  comparisonSummary,
  countryBars,
  depthDistributionBars,
  hourlyBars,
  magnitudeDistributionBars,
} from './chart-data';
import type { Statistics } from './api-types';

const HOUR = 3_600_000;
const T0 = Date.UTC(2026, 10, 16, 10, 0, 0);

function makeStats(overrides: Partial<Statistics> = {}): Statistics {
  return {
    mode: 'live',
    generated: T0,
    lastIngestion: null,
    label: null,
    lastReplayedAt: null,
    scope: 'global',
    mapTruncated: false,
    period: { start: T0, end: T0 + HOUR, defaultApplied: true },
    filters: { minMag: null, countryId: null, excludeSynthetic: false },
    unit: 'events',
    total: 0,
    hourly: { window: '1 hour UTC, end excluded', items: [] },
    byCountry: { items: [] },
    magnitudeDistribution: { unit: 'Mw', items: [], unvalued: 0 },
    depthDistribution: { unit: 'km', items: [], unvalued: 0 },
    comparison: {
      recent: { start: T0, end: T0 + HOUR, count: 0 },
      baseline: { year: 2025, events: 0, days: 365, dailyMean: 0 },
      ratio: 'ND',
      filtersApplied: [],
      warning: 'aviso',
    },
    ...overrides,
  } as Statistics;
}

describe('hourlyBars', () => {
  it('keeps empty hours with zero and formats UTC labels', () => {
    const stats = makeStats({
      total: 3,
      hourly: {
        window: 'h',
        items: [
          { start: T0, count: 3 },
          { start: T0 + HOUR, count: 0 },
        ],
      },
    });
    const r = hourlyBars(stats);
    expect(r.bars.map((b) => b.count)).toEqual([3, 0]);
    expect(r.bars[0].label).toBe('11-16 10:00');
    expect(r.hiddenWindows).toBe(0);
    expect(r.total).toBe(3);
  });

  it('shows the last 168 windows and reports the omitted ones', () => {
    const items = Array.from({ length: 200 }, (_, i) => ({ start: T0 + i * HOUR, count: i }));
    const r = hourlyBars(makeStats({ total: 999, hourly: { window: 'h', items } }));
    expect(r.bars).toHaveLength(168);
    expect(r.hiddenWindows).toBe(32);
    expect(r.bars[0].start).toBe(T0 + 32 * HOUR);
    expect(r.bars[167].count).toBe(199);
    expect(r.total).toBe(999);
  });
});

describe('countryBars', () => {
  const rows = [
    { countryId: 'A', countryName: 'Alfa', count: 10 },
    { countryId: 'B', countryName: 'Beta', count: 8 },
    { countryId: 'C', countryName: 'Gamma', count: 5 },
    { countryId: 'D', countryName: 'Delta', count: 4 },
    { countryId: null, countryName: '', count: 1 },
  ];

  it('limits to top rows, sums the rest into others and keeps allRows', () => {
    const r = countryBars(makeStats({ byCountry: { items: rows } }), 2);
    expect(r.bars.map((b) => b.countryId)).toEqual(['A', 'B', null]);
    expect(r.others).toEqual({ count: 9, countries: 2 });
    expect(r.allRows).toHaveLength(5);
  });

  it('always includes the unassigned row even outside the top', () => {
    const r = countryBars(makeStats({ byCountry: { items: rows } }), 2);
    const un = r.bars.find((b) => b.isUnassigned);
    expect(un?.label).toBe('Sin país asignado');
    expect(un?.count).toBe(1);
  });

  it('has no others when everything fits', () => {
    const r = countryBars(makeStats({ byCountry: { items: rows } }));
    expect(r.others).toBeNull();
    expect(r.bars).toHaveLength(5);
  });
});

describe('distributions', () => {
  it('keeps unvalued aside and does not add it to the bars', () => {
    const stats = makeStats({
      total: 12,
      magnitudeDistribution: { unit: 'Mw', items: [{ from: 4, to: 5, count: 7 }], unvalued: 5 },
      depthDistribution: {
        unit: 'km',
        items: [{ label: '0–70 km', from: 0, to: 70, count: 9 }],
        unvalued: 3,
      },
    });
    const m = magnitudeDistributionBars(stats);
    expect(m.bars).toEqual([{ label: '4–5', count: 7 }]);
    expect(m.unvalued).toBe(5);
    expect(m.total).toBe(12);
    const d = depthDistributionBars(stats);
    expect(d.bars).toEqual([{ label: '0–70 km', count: 9 }]);
    expect(d.unvalued).toBe(3);
  });
});

describe('barWidthPercent', () => {
  it('scales to 0..100 and is 0 when max is 0', () => {
    expect(barWidthPercent(5, 10)).toBe(50);
    expect(barWidthPercent(10, 10)).toBe(100);
    expect(barWidthPercent(0, 10)).toBe(0);
    expect(barWidthPercent(5, 0)).toBe(0);
  });
});

describe('comparisonSummary', () => {
  it('shows ND when the ratio is ND', () => {
    const r = comparisonSummary(makeStats());
    expect(r.ratioText).toBe('ND');
    expect(r.warning).toBe('aviso');
  });

  it('formats the ratio with two decimals and a decimal comma', () => {
    const stats = makeStats();
    stats.comparison.ratio = 1.5;
    stats.comparison.recent.count = 12;
    stats.comparison.baseline.dailyMean = 8;
    const r = comparisonSummary(stats);
    expect(r.ratioText).toBe('1,50');
    expect(r.recentCount).toBe(12);
    expect(r.dailyMean).toBe(8);
    expect(r.baselineYear).toBe(2025);
    expect(r.baselineDays).toBe(365);
  });
});
