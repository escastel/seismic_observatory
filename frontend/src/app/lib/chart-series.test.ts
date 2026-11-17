import { describe, expect, it } from 'vitest';
import { buildAllChartSeries, buildChartSeries, OTHERS_LABEL, REPLAY_LABEL } from './chart-series';
import { depthCategory } from './geo';
import { depthColor } from './map-layers';
import type { Statistics } from './api-types';

const HOUR = 3_600_000;
const T0 = Date.UTC(2026, 10, 16, 10, 0, 0);

function stats(o: Partial<Statistics> = {}): Statistics {
  return {
    mode: 'live', generated: T0, lastIngestion: null, label: null, lastReplayedAt: null,
    scope: 'global', mapTruncated: false,
    period: { start: T0, end: T0 + HOUR, defaultApplied: true },
    filters: { minMag: null, countryId: null, excludeSynthetic: false },
    unit: 'events', total: 10,
    hourly: { window: 'x', items: [] },
    byCountry: { items: [] },
    magnitudeDistribution: { unit: 'Mw', items: [], unvalued: 0 },
    depthDistribution: { unit: 'km', items: [], unvalued: 0 },
    comparison: {
      recent: { start: T0, end: T0 + HOUR, count: 0 },
      baseline: { year: 2025, events: 0, days: 365, dailyMean: 0 },
      ratio: 'ND', filtersApplied: [], warning: '',
    },
    ...o,
  };
}

describe('chart series', () => {
  it('returns the four charts with mandatory texts', () => {
    const all = buildAllChartSeries(stats(), 'dark');
    expect(all.map((s) => s.id)).toEqual(['hourly', 'country', 'magnitude', 'depth']);
    for (const s of all) {
      for (const t of [s.title, s.unit, s.periodText, s.filtersText, s.unvaluedText]) {
        expect(t.length).toBeGreaterThan(0);
      }
      expect(s.colors).toHaveLength(s.points.length);
      expect(s.label).toBeNull();
    }
  });

  it('marks replay mode and describes filters', () => {
    const s = buildChartSeries('country', stats({
      mode: 'replay',
      filters: { minMag: 4.5, countryId: 'CL', excludeSynthetic: true },
    }), 'light');
    expect(s.label).toBe(REPLAY_LABEL);
    expect(s.filtersText).toContain('4,5');
    expect(s.filtersText).toContain('CL');
    expect(s.filtersText).toContain('sintéticos');
  });

  it('draws 168 hours but keeps all rows in the table', () => {
    const items = Array.from({ length: 200 }, (_, i) => ({ start: T0 + i * HOUR, count: i }));
    const s = buildChartSeries('hourly', stats({ hourly: { window: 'x', items } }), 'dark');
    expect(s.points).toHaveLength(168);
    expect(s.table).toHaveLength(200);
    expect(s.notice).toContain('32');
  });

  it('keeps Sin país asignado as a row and groups the rest', () => {
    const items = [
      { countryId: null, countryName: '', count: 1 },
      { countryId: 'A', countryName: 'Alfa', count: 9 },
    ];
    const s = buildChartSeries('country', stats({ byCountry: { items } }), 'dark');
    expect(s.table.map((r) => r.label)).toContain('Sin país asignado');
    expect(s.points).toHaveLength(2);
    const many = Array.from({ length: 20 }, (_, i) => ({
      countryId: `C${i}`, countryName: `P${i}`, count: 20 - i,
    }));
    const m = buildChartSeries('country', stats({ byCountry: { items: many } }), 'dark');
    expect(m.points[m.points.length - 1].label).toContain(OTHERS_LABEL);
    expect(m.table).toHaveLength(20);
  });

  it('uses different colors per theme', () => {
    const st = stats({
      magnitudeDistribution: { unit: 'Mw', items: [{ from: 1, to: 2, count: 3 }], unvalued: 0 },
    });
    expect(buildChartSeries('magnitude', st, 'dark').colors[0]).not.toBe(
      buildChartSeries('magnitude', st, 'light').colors[0],
    );
  });

  it('colors depth like the map and adds the unvalued row', () => {
    const items = [
      { label: '0-70', from: 0, to: 70, count: 1 },
      { label: '70-300', from: 70, to: 300, count: 2 },
      { label: '300+', from: 300, to: null, count: 3 },
    ];
    const s = buildChartSeries('depth', stats({ depthDistribution: { unit: 'km', items, unvalued: 4 } }), 'light');
    expect(s.colors).toEqual([10, 100, 400].map((d) => depthColor(depthCategory(d).key, 'light')));
    const dark = buildChartSeries('depth', stats({ depthDistribution: { unit: 'km', items, unvalued: 4 } }), 'dark');
    expect(dark.colors).not.toEqual(s.colors);
    expect(s.table).toHaveLength(4);
    expect(s.table[3].count).toBe(4);
    expect(s.unvaluedText).toContain('4');
  });

  it('keeps zero counts and negative bounds', () => {
    const s = buildChartSeries('magnitude', stats({
      magnitudeDistribution: { unit: 'Mw', items: [{ from: -1, to: 0, count: 0 }], unvalued: 0 },
    }), 'dark');
    expect(s.points[0]).toEqual({ label: '-1–0', count: 0 });
  });
});
